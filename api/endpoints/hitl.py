from fastapi import APIRouter, HTTPException
from models.schemas import HITLDecisionRequest, HITLStatusResponse, OnboardingDecisionRequest
from hitl.gates import approve_shortlist, reject_shortlist, approve_pre_screening, reject_pre_screening, submit_onboarding
from db import mongodb as db
from core.logging import get_logger
from core.exceptions import SessionNotFoundError

logger = get_logger("api.hitl")
router = APIRouter(prefix="/hitl", tags=["HITL"])


def _is_waiting_for_shortlist(step: str) -> bool:
    return step in ("resumes_shortlisted",)


def _is_waiting_for_pre_screening(step: str) -> bool:
    return step in ("pre_screening_complete",)


def _is_waiting_for_onboarding(step: str) -> bool:
    return step in ("emails_sent",)


@router.get("/{session_id}/status", response_model=HITLStatusResponse)
async def get_hitl_status(session_id: str):
    """Check which HITL gate (if any) is currently waiting for approval."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    snap = session.get("state_snapshot", {})
    step = snap.get("current_step", "")

    waiting = (
        _is_waiting_for_shortlist(step)
        or _is_waiting_for_pre_screening(step)
        or _is_waiting_for_onboarding(step)
    )

    data = None
    if _is_waiting_for_shortlist(step):
        data = {
            "gate": "shortlist",
            "candidates": snap.get("shortlisted_candidates", []),
            "rationale": snap.get("shortlisting_rationale", ""),
        }
    elif _is_waiting_for_pre_screening(step):
        data = {
            "gate": "pre_screening",
            "results": snap.get("pre_screening_results", []),
        }
    elif _is_waiting_for_onboarding(step):
        data = {
            "gate": "onboarding",
            "candidates": snap.get("email_scheduling_results", []),
        }

    return HITLStatusResponse(
        session_id=session_id,
        current_step=step,
        waiting_for_approval=waiting,
        data=data,
    )


@router.post("/{session_id}/shortlist")
async def decide_shortlist(session_id: str, body: HITLDecisionRequest):
    """
    Recruiter approves or rejects the shortlisted candidates.
    - approved: graph proceeds to pre-screening calls.
    - rejected: graph re-runs the shortlisting agent (use feedback to guide re-run).
    """
    logger.info(
        "hitl_shortlist_decision",
        session_id=session_id,
        decision=body.decision,
        feedback=body.feedback,
    )
    try:
        if body.decision.value == "approved":
            await approve_shortlist(session_id, body.feedback)
        else:
            await reject_shortlist(session_id, body.feedback or "")
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"session_id": session_id, "decision": body.decision, "message": "Decision recorded. Graph resuming."}


@router.post("/{session_id}/pre-screening")
async def decide_pre_screening(session_id: str, body: HITLDecisionRequest):
    """
    Recruiter approves or rejects the pre-screening results.
    - approved: workflow is complete.
    - rejected: graph re-initiates calls to candidates.
    """
    logger.info(
        "hitl_pre_screening_decision",
        session_id=session_id,
        decision=body.decision,
        feedback=body.feedback,
    )
    try:
        if body.decision.value == "approved":
            await approve_pre_screening(session_id, body.feedback)
        else:
            await reject_pre_screening(session_id, body.feedback or "")
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"session_id": session_id, "decision": body.decision, "message": "Decision recorded. Graph resuming."}


@router.post("/{session_id}/onboarding")
async def decide_onboarding(session_id: str, body: OnboardingDecisionRequest):
    """
    HR selects which candidates cleared the interview round.
    Onboarding emails are sent to the selected candidates.
    """
    logger.info(
        "hitl_onboarding_decision",
        session_id=session_id,
        selected_count=len(body.selected_candidate_ids),
    )
    try:
        await submit_onboarding(session_id, body.selected_candidate_ids)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "session_id": session_id,
        "selected_count": len(body.selected_candidate_ids),
        "message": "Onboarding decision recorded. Emails will be sent to selected candidates.",
    }
