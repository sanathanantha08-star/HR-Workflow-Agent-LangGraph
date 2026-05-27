"""
HITL gate helpers: update LangGraph state and resume the graph.

Flow for each gate:
  1. Graph runs until interrupt_before the HITL node and pauses.
  2. API sends data to recruiter (candidates or screening results).
  3. Recruiter approves/rejects via POST endpoint.
  4. This module updates the state and resumes the graph.
"""
import asyncio
from graph.workflow import get_graph, make_config
from db import mongodb as db
from core.logging import get_logger, bind_session_log
from core.exceptions import SessionNotFoundError, HITLError

logger = get_logger("hitl.gates")


async def approve_shortlist(session_id: str, feedback: str | None = None) -> None:
    """Resume the graph with shortlist approved."""
    await _resume_with_decision(
        session_id=session_id,
        state_update={
            "shortlist_approval_status": "approved",
            "shortlist_approval_feedback": feedback,
        },
        gate_name="shortlist",
    )


async def reject_shortlist(session_id: str, feedback: str) -> None:
    """Resume the graph with shortlist rejected (triggers re-shortlisting)."""
    await _resume_with_decision(
        session_id=session_id,
        state_update={
            "shortlist_approval_status": "rejected",
            "shortlist_approval_feedback": feedback,
        },
        gate_name="shortlist",
    )


async def approve_pre_screening(session_id: str, feedback: str | None = None) -> None:
    """Resume the graph with pre-screening approved."""
    state_update = {
        "pre_screening_approval_status": "approved",
        "pre_screening_approval_feedback": feedback,
    }
    # If the pre_screening node died mid-run (results still empty), synthesize from calls
    state_update = await _maybe_recover_pre_screening(session_id, state_update)
    await _resume_with_decision(session_id=session_id, state_update=state_update, gate_name="pre_screening")


async def reject_pre_screening(session_id: str, feedback: str) -> None:
    """Resume the graph with pre-screening rejected (triggers re-calling)."""
    await _resume_with_decision(
        session_id=session_id,
        state_update={
            "pre_screening_approval_status": "rejected",
            "pre_screening_approval_feedback": feedback,
        },
        gate_name="pre_screening",
    )


async def submit_onboarding(session_id: str, selected_candidate_ids: list[str]) -> None:
    """Resume the graph with HR's onboarding candidate selection."""
    await _resume_with_decision(
        session_id=session_id,
        state_update={
            "onboarding_approval_status": "approved",
            "onboarding_selected_ids": selected_candidate_ids,
        },
        gate_name="onboarding",
    )


async def _maybe_recover_pre_screening(session_id: str, state_update: dict) -> dict:
    """
    If the pre_screening node died before writing results, synthesize them from
    the calls collection and advance the LangGraph cursor past that node so the
    graph can proceed to hitl_pre_screening normally.
    """
    session = await db.get_session(session_id)
    if not session:
        return state_update
    snap = session.get("state_snapshot", {})
    if snap.get("pre_screening_results"):
        return state_update  # results already present, nothing to recover

    calls = await db.get_session_calls(session_id)
    candidates = snap.get("shortlisted_candidates", [])
    if not calls or not candidates:
        return state_update

    calls_by_cid = {c["candidate_id"]: c for c in calls}
    results = []
    for cand in candidates:
        cid = cand["candidate_id"]
        call_doc = calls_by_cid.get(cid, {})
        sd = call_doc.get("screening_data", {})
        results.append({
            "candidate_id": cid,
            "name": cand.get("name", ""),
            "phone": cand.get("phone", ""),
            "email": cand.get("email", ""),
            "call_sid": call_doc.get("call_sid", ""),
            "call_status": call_doc.get("status", "not_initiated"),
            "looking_for_change": sd.get("looking_for_change"),
            "reason_for_change": sd.get("reason_for_change"),
            "current_ctc": sd.get("current_ctc"),
            "expected_ctc": sd.get("expected_ctc"),
            "experience_years": sd.get("experience_years"),
            "interview_slots": sd.get("interview_slots"),
        })

    logger.info("pre_screening_recovery", session_id=session_id, recovered=len(results))

    # Advance graph cursor: pretend pre_screening node just completed
    thread_id = session["thread_id"]
    config = make_config(thread_id)
    graph = get_graph()
    graph.update_state(
        config,
        {"pre_screening_results": results, "current_step": "pre_screening_complete"},
        as_node="pre_screening",
    )
    await db.update_session(session_id, {"pre_screening_results": results, "current_step": "pre_screening_complete"})

    state_update["pre_screening_results"] = results
    return state_update


async def _resume_with_decision(
    session_id: str,
    state_update: dict,
    gate_name: str,
) -> None:
    """Update state in the checkpoint then resume the graph in a background task."""
    session = await db.get_session(session_id)
    if not session:
        raise SessionNotFoundError(f"Session '{session_id}' not found")

    thread_id = session["thread_id"]
    config = make_config(thread_id)
    graph = get_graph()

    logger.info(
        "hitl_decision",
        session_id=session_id,
        gate=gate_name,
        decision=state_update,
    )

    # Update state in the checkpoint so the HITL node reads the decision
    graph.update_state(config, state_update)

    # Resume the graph asynchronously (non-blocking — graph continues in background)
    asyncio.create_task(_run_graph(graph, config, session_id))


async def _run_graph(graph, config: dict, session_id: str) -> None:
    """Resume graph execution and persist the updated state snapshot."""
    bind_session_log(session_id)   # re-attach file sink for this resumed task
    try:
        logger.info("graph_resuming", session_id=session_id)
        async for event in graph.astream(None, config, stream_mode="values"):
            step = event.get("current_step", "")
            logger.info("graph_event", session_id=session_id, step=step)
            await db.update_session(session_id, {k: v for k, v in event.items() if k != "messages"})
        logger.info("graph_completed_or_paused", session_id=session_id)
    except Exception as exc:
        logger.error("graph_resume_error", session_id=session_id, error=str(exc))
        await db.update_session(session_id, {"error": str(exc), "current_step": "error"})
