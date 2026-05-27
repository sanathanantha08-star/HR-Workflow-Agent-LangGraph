import asyncio
from functools import partial
from agents.base import BaseAgent
from tools.email_tools import send_onboarding_email
from core.logging import get_logger

logger = get_logger("agents.onboarding")


class OnboardingAgent(BaseAgent):
    """
    Sends congratulations / onboarding emails to candidates selected by HR.
    Runs after the HITL onboarding gate.
    """
    name = "onboarding"

    async def _arun(
        self,
        session_id: str,
        selected_candidates: list[dict],  # [{candidate_id, name, email, ...}]
    ) -> dict:
        logger.info(
            "onboarding_start",
            session_id=session_id,
            candidate_count=len(selected_candidates),
        )

        loop = asyncio.get_event_loop()
        results: list[dict] = []

        for candidate in selected_candidates:
            cid   = candidate.get("candidate_id", "")
            name  = candidate.get("name", "Candidate")
            email = candidate.get("email", "")

            if not email:
                logger.warning("no_email_for_candidate", candidate_id=cid, name=name)
                results.append({"candidate_id": cid, "name": name, "email": email, "status": "no_email"})
                continue

            success = await loop.run_in_executor(
                None, partial(send_onboarding_email, name, email)
            )
            status = "sent" if success else "failed"
            results.append({"candidate_id": cid, "name": name, "email": email, "status": status})
            logger.info("onboarding_email_result", candidate_id=cid, name=name, status=status)

        sent_count = sum(1 for r in results if r["status"] == "sent")
        logger.info(
            "onboarding_complete",
            session_id=session_id,
            sent=sent_count,
            total=len(results),
        )
        return {"onboarding_results": results}


onboarding_agent = OnboardingAgent()
