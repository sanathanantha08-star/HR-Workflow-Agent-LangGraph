"""
LangGraph node functions. Each node receives the full HRWorkflowState
and returns a partial dict that LangGraph merges back into the state.
"""
import time
from datetime import datetime, timezone
from langchain_core.messages import AIMessage
from models.state import HRWorkflowState
from agents.resume_shortlister import resume_shortlister_agent
from agents.pre_screener import pre_screener_agent
from tools.storage_tools import save_session_state, save_shortlisted_candidates
from core.logging import get_logger
from core.observability import build_metric
from core.exceptions import HRWorkflowError

logger = get_logger("graph.nodes")


def _history_entry(step: str, summary: str, extra: dict | None = None) -> dict:
    return {
        "step": step,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        **(extra or {}),
    }


def _agent_metric(name: str, latency_ms: float, tokens_in: int = 0, tokens_out: int = 0) -> dict:
    return {
        "name": name,
        "kind": "agent",
        "latency_ms": round(latency_ms, 2),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Node: parse_uploads ────────────────────────────────────────────────────────

async def parse_uploads_node(state: HRWorkflowState) -> dict:
    """
    Validates that resumes and JD are present in state (already stored in GridFS).
    This node is a checkpoint — actual file storage happens via the API before
    the graph is invoked.
    """
    logger.info("node_parse_uploads", session_id=state["session_id"])
    start = time.perf_counter()

    resume_count = len(state.get("resume_file_ids", []))
    jd_present = bool(state.get("job_description", "").strip())

    if resume_count == 0:
        raise HRWorkflowError("No resumes uploaded", details={"session_id": state["session_id"]})
    if not jd_present:
        raise HRWorkflowError("Job description is empty", details={"session_id": state["session_id"]})

    latency_ms = (time.perf_counter() - start) * 1000
    summary = f"Validated {resume_count} resumes and JD for session {state['session_id']}"
    logger.info("parse_uploads_complete", resume_count=resume_count, latency_ms=round(latency_ms, 2))

    return {
        "current_step": "uploads_validated",
        "workflow_history": [_history_entry("parse_uploads", summary, {"resume_count": resume_count})],
        "agent_metrics": [_agent_metric("parse_uploads_node", latency_ms)],
        "messages": [AIMessage(content=summary)],
    }


# ── Node: shortlist_resumes ────────────────────────────────────────────────────

async def shortlist_resumes_node(state: HRWorkflowState) -> dict:
    """Invoke the ResumeShortlisterAgent and save results to state + MongoDB."""
    logger.info("node_shortlist_resumes", session_id=state["session_id"])
    start = time.perf_counter()

    # Build filename list (stored in state when files were uploaded)
    filenames = state.get("resume_filenames", [])
    file_ids = state.get("resume_file_ids", [])
    if len(filenames) != len(file_ids):
        filenames = [f"resume_{i}.pdf" for i in range(len(file_ids))]

    result = await resume_shortlister_agent.arun(
        job_description=state["job_description"],
        resume_file_ids=file_ids,
        resume_filenames=filenames,
    )

    latency_ms = (time.perf_counter() - start) * 1000
    shortlisted = result["shortlisted_candidates"]
    summary = f"Shortlisted {len(shortlisted)} candidates from {len(file_ids)} resumes"

    await save_shortlisted_candidates(state["session_id"], shortlisted)

    logger.info(
        "shortlisting_complete",
        count=len(shortlisted),
        tokens_in=result.get("tokens_in"),
        tokens_out=result.get("tokens_out"),
    )

    return {
        "parsed_resumes": result["parsed_resumes"],
        "shortlisted_candidates": shortlisted,
        "shortlisting_rationale": result["shortlisting_rationale"],
        "current_step": "resumes_shortlisted",
        "shortlist_approval_status": "pending",
        "workflow_history": [
            _history_entry("shortlist_resumes", summary, {"count": len(shortlisted)})
        ],
        "agent_metrics": [
            _agent_metric(
                "resume_shortlister",
                latency_ms,
                result.get("tokens_in", 0),
                result.get("tokens_out", 0),
            )
        ],
        "messages": [AIMessage(content=summary)],
    }


# ── Node: hitl_shortlist ───────────────────────────────────────────────────────

async def hitl_shortlist_node(state: HRWorkflowState) -> dict:
    """
    Read the recruiter's shortlist approval decision (set via API before resume).
    Routes are determined by graph edges based on shortlist_approval_status.
    """
    status = state.get("shortlist_approval_status", "pending")
    feedback = state.get("shortlist_approval_feedback", "")
    logger.info("node_hitl_shortlist", status=status, session_id=state["session_id"])

    summary = f"Shortlist HITL gate: recruiter decision = {status}"
    if feedback:
        summary += f" | Feedback: {feedback}"

    return {
        "current_step": f"shortlist_{status}",
        "workflow_history": [
            _history_entry("hitl_shortlist", summary, {"decision": status, "feedback": feedback})
        ],
        "messages": [AIMessage(content=summary)],
    }


# ── Node: pre_screening ────────────────────────────────────────────────────────

async def pre_screening_node(state: HRWorkflowState) -> dict:
    """Invoke the PreScreenerAgent to call all shortlisted candidates."""
    logger.info("node_pre_screening", session_id=state["session_id"])
    start = time.perf_counter()

    result = await pre_screener_agent.arun(
        session_id=state["session_id"],
        shortlisted_candidates=state["shortlisted_candidates"],
    )

    latency_ms = (time.perf_counter() - start) * 1000
    results = result["pre_screening_results"]
    summary = f"Pre-screening calls completed for {len(results)} candidates"

    logger.info("pre_screening_complete", results_count=len(results))

    return {
        "call_sids": result["call_sids"],
        "pre_screening_results": results,
        "pre_screening_approval_status": "pending",
        "current_step": "pre_screening_complete",
        "workflow_history": [
            _history_entry("pre_screening", summary, {"results_count": len(results)})
        ],
        "agent_metrics": [
            _agent_metric("pre_screener", latency_ms)
        ],
        "messages": [AIMessage(content=summary)],
    }


# ── Node: hitl_pre_screening ───────────────────────────────────────────────────

async def hitl_pre_screening_node(state: HRWorkflowState) -> dict:
    """Read the recruiter's pre-screening approval decision."""
    status = state.get("pre_screening_approval_status", "pending")
    feedback = state.get("pre_screening_approval_feedback", "")
    logger.info("node_hitl_pre_screening", status=status, session_id=state["session_id"])

    summary = f"Pre-screening HITL gate: recruiter decision = {status}"
    if feedback:
        summary += f" | Feedback: {feedback}"

    return {
        "current_step": f"pre_screening_{status}",
        "workflow_history": [
            _history_entry("hitl_pre_screening", summary, {"decision": status, "feedback": feedback})
        ],
        "messages": [AIMessage(content=summary)],
    }
