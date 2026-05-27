from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum


class ApprovalDecision(str, Enum):
    approved = "approved"
    rejected = "rejected"


# ── Upload ─────────────────────────────────────────────────────────────────────

class StartWorkflowResponse(BaseModel):
    session_id: str
    thread_id: str
    message: str


# ── Candidate (from resume parsing) ───────────────────────────────────────────

class ParsedResume(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    skills: list[str] = Field(default_factory=list)
    current_role: str = ""
    education: str = ""
    raw_text: str = ""
    file_id: str = ""


class ShortlistedCandidate(BaseModel):
    candidate_id: str
    name: str
    email: str
    phone: str
    skills: list[str]
    current_role: str
    selection_reason: str
    match_score: float = Field(ge=0.0, le=10.0)


class ShortlistResult(BaseModel):
    candidates: list[ShortlistedCandidate]
    rationale: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0


# ── HITL ───────────────────────────────────────────────────────────────────────

class HITLDecisionRequest(BaseModel):
    decision: ApprovalDecision
    feedback: Optional[str] = None

    @field_validator("feedback")
    @classmethod
    def feedback_required_on_rejection(cls, v, info):
        if info.data.get("decision") == ApprovalDecision.rejected and not v:
            raise ValueError("Feedback is required when rejecting")
        return v


class HITLStatusResponse(BaseModel):
    session_id: str
    current_step: str
    waiting_for_approval: bool
    data: Optional[dict] = None


# ── Pre-screening ──────────────────────────────────────────────────────────────

class PreScreeningData(BaseModel):
    candidate_id: str
    name: str
    phone: str
    looking_for_change: Optional[bool] = None
    reason_for_change: Optional[str] = None
    current_ctc: Optional[str] = None
    expected_ctc: Optional[str] = None
    experience_years: Optional[str] = None
    interview_slots: Optional[list[str]] = None  # e.g. ["Available on Monday, May 25 from 8 AM to 12 PM"]
    call_sid: str = ""
    call_status: str = "initiated"   # initiated | completed | failed | no_answer


# ── Call webhook payloads (Twilio) ─────────────────────────────────────────────

class TwilioVoiceWebhook(BaseModel):
    CallSid: str
    CallStatus: str
    To: str = ""
    From: str = ""
    SpeechResult: Optional[str] = None
    Confidence: Optional[str] = None


class TwilioGatherResult(BaseModel):
    CallSid: str
    SpeechResult: Optional[str] = None
    Confidence: Optional[str] = None


# ── Onboarding ─────────────────────────────────────────────────────────────────

class OnboardingDecisionRequest(BaseModel):
    selected_candidate_ids: list[str]


# ── Workflow status ────────────────────────────────────────────────────────────

class WorkflowStatusResponse(BaseModel):
    session_id: str
    current_step: str
    shortlist_approval_status: str
    pre_screening_approval_status: str
    onboarding_approval_status: str = "pending"
    shortlisted_candidates: list[dict]
    pre_screening_results: list[dict]
    email_scheduling_results: list[dict] = []
    onboarding_results: list[dict] = []
    workflow_history: list[dict]
    error: Optional[str] = None
