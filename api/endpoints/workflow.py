import uuid
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from typing import Annotated
from models.schemas import StartWorkflowResponse, WorkflowStatusResponse
from models.state import initial_state
from graph.workflow import get_graph, make_config
from db import mongodb as db
from tools.storage_tools import store_file_bytes
from core.logging import get_logger, bind_session_log
from core.exceptions import SessionNotFoundError

logger = get_logger("api.workflow")
router = APIRouter(prefix="/workflow", tags=["Workflow"])


@router.post("/start", response_model=StartWorkflowResponse)
async def start_workflow(
    jd_file: Annotated[UploadFile, File(description="Job description file (.pdf/.docx/.txt)")],
    resume_files: Annotated[list[UploadFile], File(description="Resume files (up to 100)")],
):
    """
    Upload the JD and resumes to kick off the HR workflow.
    Files are stored in MongoDB GridFS. The LangGraph graph starts in background.
    Returns session_id and thread_id for tracking.
    """
    session_id = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())
    logger.info("workflow_start", session_id=session_id, num_resumes=len(resume_files))

    # ── Store JD ──────────────────────────────────────────────────────────
    jd_bytes = await jd_file.read()
    jd_file_id = await store_file_bytes(
        jd_file.filename or "jd.pdf", jd_bytes, {"type": "jd", "session_id": session_id}
    )

    # ── Extract JD text immediately (for state) ───────────────────────────
    from tools.file_tools import extract_text_from_file
    jd_text = extract_text_from_file(jd_file.filename or "jd.pdf", jd_bytes)

    # ── Store resumes in parallel ─────────────────────────────────────────
    async def _store_resume(f: UploadFile) -> tuple[str, str]:
        content = await f.read()
        fid = await store_file_bytes(
            f.filename or "resume.pdf", content, {"type": "resume", "session_id": session_id}
        )
        return fid, f.filename or "resume.pdf"

    stored = await asyncio.gather(*[_store_resume(f) for f in resume_files])
    resume_file_ids = [s[0] for s in stored]
    resume_filenames = [s[1] for s in stored]

    # ── Build initial state ───────────────────────────────────────────────
    state = initial_state(session_id, thread_id)
    state["job_description"] = jd_text
    state["jd_file_id"] = jd_file_id
    state["resume_file_ids"] = resume_file_ids
    state["resume_filenames"] = resume_filenames  # type: ignore[typeddict-unknown-key]

    # ── Persist session record ────────────────────────────────────────────
    await db.create_session(session_id, thread_id, {k: v for k, v in state.items() if k != "messages"})

    # ── Start graph in background ─────────────────────────────────────────
    asyncio.create_task(_run_initial_graph(state, session_id, thread_id))

    logger.info("workflow_started", session_id=session_id, thread_id=thread_id)
    return StartWorkflowResponse(
        session_id=session_id,
        thread_id=thread_id,
        message="Workflow started. Resumes are being analyzed.",
    )


async def _run_initial_graph(state: dict, session_id: str, thread_id: str) -> None:
    """Run graph from START until first interrupt (before hitl_shortlist)."""
    bind_session_log(session_id)   # opens logs/<session_id>.jsonl, tags all logs in this task
    config = make_config(thread_id)
    graph = get_graph()
    try:
        async for event in graph.astream(state, config, stream_mode="values"):
            step = event.get("current_step", "")
            logger.info("graph_event", session_id=session_id, step=step)
            await db.update_session(session_id, {k: v for k, v in event.items() if k != "messages"})
        logger.info("graph_paused_at_hitl", session_id=session_id)
    except Exception as exc:
        logger.error("graph_initial_run_error", session_id=session_id, error=str(exc))
        await db.update_session(session_id, {"error": str(exc), "current_step": "error"})


@router.get("/{session_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(session_id: str):
    """Get the current workflow status and all collected data."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    snap = session.get("state_snapshot", {})
    return WorkflowStatusResponse(
        session_id=session_id,
        current_step=snap.get("current_step", "unknown"),
        shortlist_approval_status=snap.get("shortlist_approval_status", "pending"),
        pre_screening_approval_status=snap.get("pre_screening_approval_status", "pending"),
        onboarding_approval_status=snap.get("onboarding_approval_status", "pending"),
        shortlisted_candidates=snap.get("shortlisted_candidates", []),
        pre_screening_results=snap.get("pre_screening_results", []),
        email_scheduling_results=snap.get("email_scheduling_results", []),
        onboarding_results=snap.get("onboarding_results", []),
        workflow_history=snap.get("workflow_history", []),
        error=snap.get("error"),
    )


@router.get("/{session_id}/shortlist")
async def get_shortlist(session_id: str):
    """Return the shortlisted candidates awaiting HITL approval."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    snap = session.get("state_snapshot", {})
    return {
        "session_id": session_id,
        "current_step": snap.get("current_step"),
        "shortlist_approval_status": snap.get("shortlist_approval_status", "pending"),
        "shortlisting_rationale": snap.get("shortlisting_rationale", ""),
        "candidates": snap.get("shortlisted_candidates", []),
    }


@router.get("/{session_id}/pre-screening")
async def get_pre_screening_results(session_id: str):
    """Return pre-screening call results awaiting HITL approval."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    snap = session.get("state_snapshot", {})
    calls = await db.get_session_calls(session_id)
    return {
        "session_id": session_id,
        "pre_screening_approval_status": snap.get("pre_screening_approval_status", "pending"),
        "results": snap.get("pre_screening_results", []),
        "call_details": calls,
    }


@router.get("/{session_id}/report", response_class=HTMLResponse)
async def get_workflow_report(session_id: str):
    """Generate and return the full HTML run log report for this session."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    from generate_report import build_report
    html = await build_report(session_id)
    return HTMLResponse(content=html)
