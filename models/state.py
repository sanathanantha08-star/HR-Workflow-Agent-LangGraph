import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class HRWorkflowState(TypedDict):
    # ── Session ────────────────────────────────────────────────────────────
    session_id: str
    thread_id: str

    # ── Recruiter uploads ──────────────────────────────────────────────────
    job_description: str                    # raw JD text
    jd_file_id: Optional[str]              # GridFS file id of JD
    resume_file_ids: list[str]             # GridFS file ids of resumes
    resume_filenames: list[str]            # original filenames (parallel to resume_file_ids)

    # ── Resume processing ──────────────────────────────────────────────────
    parsed_resumes: list[dict]             # [{name, email, phone, skills, exp, raw_text}, ...]
    shortlisted_candidates: list[dict]     # top-N candidates with selection_reason
    shortlisting_rationale: str            # overall rationale from agent

    # ── HITL: shortlist ────────────────────────────────────────────────────
    shortlist_approval_status: str         # "pending" | "approved" | "rejected"
    shortlist_approval_feedback: Optional[str]

    # ── Pre-screening calls ────────────────────────────────────────────────
    call_sids: list[str]                   # Twilio call SIDs initiated
    pre_screening_results: list[dict]      # [{candidate_id, looking_for_change, reason,
                                           #   current_ctc, expected_ctc, interview_slots, call_sid}]

    # ── HITL: pre-screening ────────────────────────────────────────────────
    pre_screening_approval_status: str     # "pending" | "approved" | "rejected"
    pre_screening_approval_feedback: Optional[str]

    # ── Interview scheduling ───────────────────────────────────────────────
    email_scheduling_results: list[dict]   # [{candidate_id, name, email, status, scheduled_slot, calendar_link}]

    # ── HITL: onboarding ──────────────────────────────────────────────────
    onboarding_approval_status: str        # "pending" | "approved"
    onboarding_selected_ids: list[str]     # candidate_ids HR selected as cleared
    onboarding_results: list[dict]         # [{candidate_id, name, email, status}]

    # ── Workflow tracking ──────────────────────────────────────────────────
    current_step: str
    workflow_history: Annotated[list[dict], operator.add]
    error: Optional[str]

    # ── Observability (accumulated across nodes) ───────────────────────────
    agent_metrics: Annotated[list[dict], operator.add]
    tool_metrics: Annotated[list[dict], operator.add]

    # ── LangGraph messages ─────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]


def initial_state(session_id: str, thread_id: str) -> HRWorkflowState:
    return HRWorkflowState(
        session_id=session_id,
        thread_id=thread_id,
        job_description="",
        jd_file_id=None,
        resume_file_ids=[],
        resume_filenames=[],
        parsed_resumes=[],
        shortlisted_candidates=[],
        shortlisting_rationale="",
        shortlist_approval_status="pending",
        shortlist_approval_feedback=None,
        call_sids=[],
        pre_screening_results=[],
        pre_screening_approval_status="pending",
        pre_screening_approval_feedback=None,
        email_scheduling_results=[],
        onboarding_approval_status="pending",
        onboarding_selected_ids=[],
        onboarding_results=[],
        current_step="initialized",
        workflow_history=[],
        error=None,
        agent_metrics=[],
        tool_metrics=[],
        messages=[],
    )
