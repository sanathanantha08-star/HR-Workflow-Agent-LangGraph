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

        call_sids: list[str] = []

        # ── Step 1: Initiate calls to all candidates ───────────────────────
        for candidate in shortlisted_candidates:
            phone = candidate.get("phone", "").strip()
            candidate_id = candidate.get("candidate_id", "")
            name = candidate.get("name", "Candidate")

            if not phone:
                logger.warning("no_phone_for_candidate", candidate_id=candidate_id, name=name)
                # Create a failed call record so we can track it
                await db.create_call_record(
                    session_id, candidate_id, f"no_phone_{candidate_id}", phone or "N/A"
                )
                await db.update_call_record(
                    f"no_phone_{candidate_id}",
                    {"status": "failed", "screening_data": {"error": "No phone number available"}},
                )
                continue

            try:
                # Run sync Twilio call in thread pool so it doesn't block the event loop
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, partial(initiate_outbound_call, phone, name, session_id)
                )
                call_sid = result["call_sid"]
                call_sids.append(call_sid)
                await create_call_record(session_id, candidate_id, call_sid, phone)
                logger.info("call_initiated_for_candidate", candidate_id=candidate_id, call_sid=call_sid)
            except Exception as exc:
                logger.error(
                    "call_initiation_failed",
                    candidate_id=candidate_id,
                    phone=phone,
                    error=str(exc),
                    exc_info=True,
                )
                # Record the failure so we don't poll forever waiting for it
                await db.create_call_record(session_id, candidate_id, f"failed_{candidate_id}", phone)
                await db.update_call_record(
                    f"failed_{candidate_id}",
                    {"status": "failed", "screening_data": {"error": str(exc)}},
                )

        # ── Step 2: Poll until all calls complete or timeout ───────────────
        pre_screening_results = await self._wait_for_calls(session_id, shortlisted_candidates)

        logger.info(
            "pre_screener_complete",
            session_id=session_id,
            results_count=len(pre_screening_results),
            call_sids=call_sids,
        )
        return {
            "call_sids": call_sids,
            "pre_screening_results": pre_screening_results,
            "tokens_in": 0,
            "tokens_out": 0,
        }

    async def _wait_for_calls(
        self, session_id: str, candidates: list[dict]
    ) -> list[dict]:
        """Poll MongoDB until all candidate calls have a terminal status."""
        deadline = time.time() + _settings.call_max_wait_minutes * 60
        interval = _settings.call_polling_interval_seconds
        expected_count = len(candidates)

        while time.time() < deadline:
            call_docs = await db.get_session_calls(session_id)
            completed = [
                d for d in call_docs
                if d.get("status") in ("completed", "failed", "no_answer", "busy", "no-answer")
            ]
            logger.info(
                "polling_calls",
                session_id=session_id,
                completed=len(completed),
                expected=expected_count,
            )
            if len(completed) >= expected_count:
                return self._build_results(candidates, call_docs)
            await asyncio.sleep(interval)

        logger.warning(
            "call_wait_timeout",
            session_id=session_id,
            timeout_minutes=_settings.call_max_wait_minutes,
        )
        # Return whatever we have even on timeout
        call_docs = await db.get_session_calls(session_id)
        return self._build_results(candidates, call_docs)

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
                "availability": screening.get("availability"),
            })
        return results


pre_screener_agent = PreScreenerAgent()
