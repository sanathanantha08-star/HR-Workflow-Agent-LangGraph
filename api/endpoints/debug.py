"""
Debug helpers — only for local testing.
POST /api/debug/skip-to-onboarding creates a session with mock email-scheduling
results and fast-forwards the LangGraph checkpoint to the hitl_onboarding pause
so the onboarding UI can be exercised without running calls or email-scheduler.
"""
import uuid
import asyncio
from fastapi import APIRouter
from graph.workflow import get_graph, make_config
from db import mongodb as db
from core.logging import get_logger

logger = get_logger("api.debug")
router = APIRouter(prefix="/debug", tags=["Debug"])

_MOCK_SCHEDULING = [
    {
        "candidate_id": "debug_cand_001",
        "name": "Aditya Kumar",
        "email": "sanath.anantha08@gmail.com",
        "phone": "+91-9876543210",
        "status": "scheduled",
        "scheduled_slot": "Monday, June 2, 2026 10:00 AM – 11:00 AM IST",
        "calendar_link": "",
    },
    {
        "candidate_id": "debug_cand_002",
        "name": "Priya Sharma",
        "email": "sanath.anantha07@gmail.com",
        "phone": "+91-9123456789",
        "status": "scheduled",
        "scheduled_slot": "Tuesday, June 3, 2026 2:00 PM – 3:00 PM IST",
        "calendar_link": "",
    },
    {
        "candidate_id": "debug_cand_003",
        "name": "Rahul Verma",
        "email": "",
        "phone": "+91-9000000001",
        "status": "no_slots",
        "scheduled_slot": "",
        "calendar_link": "",
    },
]


@router.post("/skip-to-onboarding")
async def skip_to_onboarding():
    """
    Create a fresh session pre-loaded with mock interview-scheduling results
    and advance the graph to the hitl_onboarding interrupt point.
    Returns the session_id — load it in the UI with localStorage or the chip.
    """
    session_id = f"debug_{uuid.uuid4().hex[:10]}"
    thread_id  = f"thread_{uuid.uuid4().hex}"
    config     = make_config(thread_id)

    mock_state = {
        "session_id": session_id,
        "job_description": "[DEBUG] Software Engineer — mock JD",
        "resume_file_ids": [],
        "resume_filenames": [],
        "parsed_resumes": [],
        "shortlisted_candidates": [
            {
                "candidate_id": r["candidate_id"],
                "name": r["name"],
                "email": r["email"],
                "phone": r["phone"],
                "skills": ["Python", "FastAPI"],
                "current_role": "Software Engineer",
                "selection_reason": "Debug candidate",
                "match_score": 8.0,
            }
            for r in _MOCK_SCHEDULING
        ],
        "shortlisting_rationale": "Debug run — mock data",
        "shortlist_approval_status": "approved",
        "shortlist_approval_feedback": "debug skip",
        "call_sids": [],
        "pre_screening_results": [
            {
                "candidate_id": r["candidate_id"],
                "name": r["name"],
                "phone": r["phone"],
                "email": r["email"],
                "call_status": "completed",
                "looking_for_change": True,
                "reason_for_change": "Better growth opportunity",
                "current_ctc": "12 LPA",
                "expected_ctc": "18 LPA",
                "experience_years": "4 years",
                "interview_slots": ["Mon 10 AM – 12 PM", "Tue 2 PM – 4 PM"],
            }
            for r in _MOCK_SCHEDULING
        ],
        "pre_screening_approval_status": "approved",
        "pre_screening_approval_feedback": "debug skip",
        "email_scheduling_results": _MOCK_SCHEDULING,
        "onboarding_approval_status": "pending",
        "onboarding_selected_ids": [],
        "onboarding_results": [],
        "current_step": "emails_sent",
        "workflow_history": [
            {"step": "debug", "timestamp": "2026-01-01T00:00:00+00:00",
             "summary": "Debug session — skipped to onboarding gate"},
        ],
        "agent_metrics": [],
        "messages": [],
        "error": None,
    }

    # Create MongoDB session record
    await db.create_session(session_id, thread_id, mock_state)

    # Inject state into LangGraph checkpoint positioned after email_interview_scheduler,
    # then run the graph so it creates a proper "interrupted before hitl_onboarding"
    # checkpoint. Without the astream call, the interrupt marker is never written and
    # submit_onboarding's resume call restarts from START instead.
    # hitl_onboarding runs once (LangGraph quirk with update_state+as_node) setting
    # current_step="onboarding_pending" before the interrupt fires on the second visit —
    # the frontend maps "onboarding_pending" to the onboarding view, so this is fine.
    graph = get_graph()
    graph.update_state(config, mock_state, as_node="email_interview_scheduler")
    asyncio.create_task(_advance(graph, config, session_id))

    logger.info("debug_skip_to_onboarding", session_id=session_id)
    return {"session_id": session_id, "thread_id": thread_id}


async def _advance(graph, config: dict, session_id: str) -> None:
    try:
        async for event in graph.astream(None, config, stream_mode="values"):
            step = event.get("current_step", "")
            logger.info("debug_graph_event", session_id=session_id, step=step)
            await db.update_session(session_id, {k: v for k, v in event.items() if k != "messages"})
        logger.info("debug_graph_paused", session_id=session_id)
    except Exception as exc:
        logger.error("debug_graph_error", session_id=session_id, error=str(exc))
