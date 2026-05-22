# Agentic HR Workflow

A fully autonomous, multi-agent HR workflow system that takes a job description and a batch of resumes, shortlists the best candidates using AI, conducts live voice pre-screening calls, and produces a complete run log — all with human-in-the-loop approval gates at each stage.

---

## What This System Does

### End-to-End Flow

```
Recruiter uploads JD + Resumes
        ↓
[Agent 1] Resume Shortlister
  - Parses PDF/DOCX resumes (pdfplumber, python-docx)
  - Ranks candidates against JD using Cohere LLM
  - Returns top 5 with match score + selection reason
        ↓
[HITL Gate 1] Recruiter approves/rejects shortlist
        ↓
[Agent 2] Pre-Screening Call Agent
  - Dials each shortlisted candidate via Twilio outbound call
  - AI voice agent conducts a live phone conversation
  - Collects: job change intent, reason, current CTC, expected CTC, availability
  - Uses Edge TTS (Microsoft Neural, free) for natural voice
  - Uses Twilio <Gather input="speech"> for real-time STT
        ↓
[HITL Gate 2] Recruiter reviews call results and approves
        ↓
Workflow Complete → HTML Run Log generated
```

### What Was Actually Achieved

This is a **working, production-tested system**. A real end-to-end run was completed:

- Resume uploaded: `Sanath_Anantha_Resume_sde.pdf`
- Candidate shortlisted with match score **9/10** for a Software Engineer role
- Recruiter approved shortlist via REST API
- System placed a **live Twilio call to +918951523420**
- AI agent conducted a full pre-screening conversation (5+ turns)
- Collected all screening data:
  - Looking for change: **Yes**
  - Reason: *Better opportunities and a better package*
  - Current CTC: **6 lakhs**
  - Expected CTC: **14 lakhs**
  - Availability: **May 24th, 8:00 a.m.**
- Recruiter approved pre-screening results
- Final status: `pre_screening_approved`
- HTML run log generated with full transcript

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (StateGraph with interrupt-based HITL) |
| LLM | Cohere `command-r-plus-08-2024` via langchain-cohere |
| Voice calls | Twilio outbound calls + `<Gather input="speech">` STT |
| TTS | Edge TTS (Microsoft Neural, free) |
| Database | MongoDB (motor async) + GridFS for file storage |
| API | FastAPI with lifespan, static file serving |
| Observability | structlog JSON logging, latency + token tracking on every LLM call |
| Retries | tenacity exponential backoff on all external calls |
| Validation | Pydantic v2 settings + request/response schemas |
| Webhooks | ngrok tunnel for local Twilio webhook delivery |

---

## Project Structure

```
agentic-hr/
├── main.py                    # FastAPI app entry point
├── config/settings.py         # Pydantic settings (env vars)
├── core/
│   ├── logging.py             # structlog JSON setup
│   ├── observability.py       # @observe_agent, @observe_tool decorators
│   └── exceptions.py          # Custom exceptions + FastAPI handlers
├── db/mongodb.py              # All MongoDB operations (async/motor)
├── models/
│   ├── state.py               # LangGraph HRWorkflowState TypedDict
│   └── schemas.py             # Pydantic request/response schemas
├── tools/
│   ├── base.py                # @tool_call, @with_retry decorators
│   ├── file_tools.py          # PDF/DOCX text extraction
│   ├── llm_tools.py           # Cohere LLM wrappers
│   └── call_tools.py          # Twilio outbound call initiator
├── agents/
│   ├── resume_shortlister.py  # Resume parsing + LLM ranking node
│   └── pre_screener.py        # Call orchestration + polling node
├── graph/
│   ├── workflow.py            # StateGraph definition + compilation
│   └── edges.py               # Conditional routing after HITL gates
├── hitl/gates.py              # HITL decision handlers (approve/reject)
├── voice/
│   ├── conversation.py        # TwiML state machine for live calls
│   └── tts.py                 # Edge TTS audio generation
├── api/endpoints/
│   ├── workflow.py            # /workflow/* REST endpoints
│   ├── hitl.py                # /hitl/* REST endpoints
│   └── webhooks.py            # /webhooks/twilio/* Twilio callbacks
├── generate_report.py         # HTML run log generator
├── test_call.py               # Standalone Twilio call tester
├── test_flow.sh               # End-to-end bash test script
├── .env.example               # Environment variable template
└── requirements.txt
```

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your real API keys
```

You need:
- **Cohere API key** — free at [cohere.com](https://cohere.com)
- **Twilio account** — free trial at [twilio.com](https://twilio.com) (verify your phone number)
- **MongoDB** — local or Atlas (default: `mongodb://localhost:27017`)

### 3. Start ngrok

```bash
ngrok http 8000
# Copy the https URL into .env as PUBLIC_BASE_URL
```

Configure your Twilio phone number's Voice webhook to:
`https://<your-ngrok-url>/api/webhooks/twilio/voice`

### 4. Run the server

```bash
python main.py
```

---

## Running the Workflow

### Option A — bash script (recommended for testing)

```bash
bash test_flow.sh /path/to/resume.pdf
```

This walks through the full flow interactively: upload → shortlist review → HITL → call → HITL → complete.

### Option B — curl manually

```bash
# 1. Start workflow
curl -X POST http://localhost:8000/api/workflow/start \
  -F "jd_file=@job_description.txt" \
  -F "resume_files=@resume.pdf"

# 2. Check status / shortlist
curl http://localhost:8000/api/workflow/<session_id>/shortlist

# 3. Approve shortlist
curl -X POST http://localhost:8000/api/hitl/<session_id>/shortlist \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "feedback": "Looks good"}'

# 4. Check pre-screening results
curl http://localhost:8000/api/workflow/<session_id>/pre-screening

# 5. Approve pre-screening
curl -X POST http://localhost:8000/api/hitl/<session_id>/pre-screening \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "feedback": "Ready for interview"}'
```

### Generating the HTML Run Log

```bash
python generate_report.py <session_id>
open run_log_<first8chars>.html
```

---

## Key Design Decisions

- **LangGraph `interrupt_before`** — HITL gates pause graph execution cleanly; `MemorySaver` holds checkpoint state while MongoDB holds business data persistently.
- **Twilio + Edge TTS** — Twilio handles telephony (STT via `<Gather input="speech">`); Edge TTS generates the AI voice as MP3 served from FastAPI's `/static` endpoint, keeping voice costs at zero.
- **Async-first** — All I/O is async (motor for MongoDB, async FastAPI). Twilio's sync SDK is wrapped with `run_in_executor` to avoid blocking the event loop.
- **TwiML XML escaping** — `&` between query params in TwiML action URLs must be escaped as `&amp;`; handled by `_action_url()` in `voice/conversation.py`.
- **Structured observability** — Every LLM call logs `tokens_in`, `tokens_out`, `latency_ms`. Every agent node emits a structured metric. All logs are JSON via structlog.
