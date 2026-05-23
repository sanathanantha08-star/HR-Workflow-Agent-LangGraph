import asyncio
import time
from functools import partial
from agents.base import BaseAgent
from tools.call_tools import initiate_outbound_call
from tools.storage_tools import create_call_record
from config.settings import get_settings
from core.logging import get_logger
from db import mongodb as db

logger = get_logger("agents.pre_screener")
_settings = get_settings()


class PreScreenerAgent(BaseAgent):
    """
    Initiates Twilio outbound calls to each shortlisted candidate.
    Waits (polling MongoDB) until all calls complete or timeout, then
    returns the collected pre-screening data.
    """
    name = "pre_screener"

    async def _arun(
        self,
        session_id: str,
        shortlisted_candidates: list[dict],
    ) -> dict:
        logger.info(
            "pre_screener_start",
            session_id=session_id,
            candidate_count=len(shortlisted_candidates),
        )

        # ── Step 1: Call each candidate sequentially: initiate → wait → next ─
        call_sids: list[str] = []
        for candidate in shortlisted_candidates:
            sid = await self._initiate_call(session_id, candidate)
            if sid:
                call_sids.append(sid)
            # Block until this call finishes before dialling the next one
            await self._wait_for_one_call(session_id, candidate["candidate_id"])
            await asyncio.sleep(3)  # brief pause so webhooks drain before next call

        # ── Step 2: Build final results from completed call records ───────
        call_docs = await db.get_session_calls(session_id)
        pre_screening_results = self._build_results(shortlisted_candidates, call_docs)

        logger.info(
            "pre_screener_complete",
            session_id=session_id,
            results_count=len(pre_screening_results),
            calls_initiated=len(call_sids),
        )
        return {
            "call_sids": call_sids,
            "pre_screening_results": pre_screening_results,
            "tokens_in": 0,
            "tokens_out": 0,
        }

    async def _initiate_call(self, session_id: str, candidate: dict) -> str | None:
        """Initiate a single Twilio call and create its DB record. Returns call_sid or None."""
        phone        = candidate.get("phone", "").strip()
        candidate_id = candidate.get("candidate_id", "")
        name         = candidate.get("name", "Candidate")

        if not phone:
            logger.warning("no_phone_for_candidate", session_id=session_id, candidate_id=candidate_id, name=name)
            await db.create_call_record(session_id, candidate_id, f"no_phone_{candidate_id}", "N/A")
            await db.update_call_record(f"no_phone_{candidate_id}", {"status": "failed", "screening_data": {"error": "No phone number"}})
            return None

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, partial(initiate_outbound_call, phone, name, session_id)
            )
            call_sid = result["call_sid"]
            await create_call_record(session_id, candidate_id, call_sid, phone)
            logger.info("call_initiated", session_id=session_id, candidate_id=candidate_id, call_sid=call_sid)
            return call_sid
        except Exception as exc:
            logger.error("call_initiation_failed", session_id=session_id, candidate_id=candidate_id, error=str(exc))
            await db.create_call_record(session_id, candidate_id, f"failed_{candidate_id}", phone)
            await db.update_call_record(f"failed_{candidate_id}", {"status": "failed", "screening_data": {"error": str(exc)}})
            return None

    async def _wait_for_one_call(self, session_id: str, candidate_id: str) -> None:
        """Block until the given candidate's call reaches a terminal status or times out."""
        terminal = {"completed", "failed", "no_answer", "no-answer", "busy", "canceled"}
        deadline = time.time() + _settings.call_max_wait_minutes * 60
        interval = _settings.call_polling_interval_seconds

        while time.time() < deadline:
            call_docs = await db.get_session_calls(session_id)
            for doc in call_docs:
                if doc.get("candidate_id") == candidate_id and doc.get("status") in terminal:
                    logger.info(
                        "call_finished",
                        session_id=session_id,
                        candidate_id=candidate_id,
                        status=doc["status"],
                    )
                    return
            logger.info("waiting_for_call", session_id=session_id, candidate_id=candidate_id)
            await asyncio.sleep(interval)

        logger.warning(
            "single_call_timeout",
            session_id=session_id,
            candidate_id=candidate_id,
            timeout_minutes=_settings.call_max_wait_minutes,
        )

    def _build_results(self, candidates: list[dict], call_docs: list[dict]) -> list[dict]:
        """Merge candidate data with call screening results."""
        calls_by_candidate = {d["candidate_id"]: d for d in call_docs}
        results = []
        for c in candidates:
            cid = c["candidate_id"]
            call_doc = calls_by_candidate.get(cid, {})
            screening = call_doc.get("screening_data", {})
            results.append({
                "candidate_id": cid,
                "name": c.get("name", ""),
                "phone": c.get("phone", ""),
                "email": c.get("email", ""),
                "call_sid": call_doc.get("call_sid", ""),
                "call_status": call_doc.get("status", "not_initiated"),
                "looking_for_change": screening.get("looking_for_change"),
                "reason_for_change": screening.get("reason_for_change"),
                "current_ctc": screening.get("current_ctc"),
                "expected_ctc": screening.get("expected_ctc"),
                "experience_years": screening.get("experience_years"),
                "interview_slots": screening.get("interview_slots"),
            })
        return results


pre_screener_agent = PreScreenerAgent()
