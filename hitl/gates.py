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
from core.logging import get_logger
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
    await _resume_with_decision(
        session_id=session_id,
        state_update={
            "pre_screening_approval_status": "approved",
            "pre_screening_approval_feedback": feedback,
        },
        gate_name="pre_screening",
    )


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
