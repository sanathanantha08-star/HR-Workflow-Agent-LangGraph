from langgraph.graph import END
from models.state import HRWorkflowState
from core.logging import get_logger

logger = get_logger("graph.edges")


def route_after_shortlist_hitl(state: HRWorkflowState) -> str:
    """
    After the HITL shortlist gate:
    - approved  → proceed to pre-screening calls
    - rejected  → redo shortlisting (agent may adjust with feedback)
    - pending   → should not happen; stay (graph will pause via interrupt_before)
    """
    status = state.get("shortlist_approval_status", "pending")
    logger.info("route_shortlist_hitl", status=status, session_id=state.get("session_id"))

    if status == "approved":
        return "pre_screening"
    elif status == "rejected":
        return "shortlist_resumes"
    # Safety fallback — treat unknown as needing re-approval
    return "hitl_shortlist"


def route_after_pre_screening_hitl(state: HRWorkflowState) -> str:
    """
    After the HITL pre-screening gate:
    - approved  → schedule interviews and send emails
    - rejected  → redo pre-screening calls
    """
    status = state.get("pre_screening_approval_status", "pending")
    logger.info("route_pre_screening_hitl", status=status, session_id=state.get("session_id"))

    if status == "approved":
        return "email_interview_scheduler"
    elif status == "rejected":
        return "pre_screening"
    return "hitl_pre_screening"


def route_after_onboarding_hitl(state: HRWorkflowState) -> str:
    """After onboarding HITL gate: approved → send emails, otherwise wait."""
    status = state.get("onboarding_approval_status", "pending")
    logger.info("route_onboarding_hitl", status=status, session_id=state.get("session_id"))

    if status == "approved":
        return "onboarding"
    return "hitl_onboarding"
