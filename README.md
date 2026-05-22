# Agentic HR — AI-Powered Recruitment Pipeline

An end-to-end autonomous recruitment pipeline built with multi-agent AI. The system replaces repetitive HR coordination tasks with a chain of specialised AI agents, each handling one stage of the hiring process — while keeping humans in control at every decision point through built-in approval gates.

---

## What This Project Does

A recruiter uploads a job description and a batch of resumes. From that moment, a multi-agent pipeline takes over:

1. **Orchestrator Agent** receives the trigger and coordinates the entire pipeline, routing work between specialised agents and surfacing decisions to the recruiter when human judgment is needed.

2. **Resume Shortlister Agent** reads every resume, scores each candidate against the job description, and produces a ranked shortlist of 10–15 candidates with a match score and selection rationale for each. The shortlist is sent to the recruiter for approval (HITL gate).

3. **Pre-Screening Call Agent** — after the recruiter approves the shortlist — calls each shortlisted candidate over the phone using a live AI voice agent. It conducts a natural conversation and collects: job change intent, reason for change, current CTC, expected CTC, and availability for an interview slot. The collected data is sent back to the recruiter for approval (HITL gate).

4. **Interview Scheduler Agent** *(planned)* takes the approved pre-screening results and automatically schedules interviews between the candidate and the interviewer based on their declared availability.

5. **Background Verification Agent** *(planned)* initiates and tracks BGV checks once the interview stage is cleared.

6. **Onboarding Agent** *(planned)* handles all post-offer onboarding logistics — document collection, system access, induction scheduling, etc.

> In the future this pipeline can be extended with offer management, multiple interview rounds, ATS integrations, custom screening questionnaires, and per-company workflow configuration. The architecture is built to support that from day one.

---

## Architecture

```
                        ┌─────────────────────────────────┐
                        │         RECRUITER / HR           │
                        │  (uploads JD + resumes, reviews │
                        │   shortlists, approves results)  │
                        └────────────┬────────────────────┘
                                     │  trigger
                                     ▼
                        ┌─────────────────────────────┐
                        │      Orchestrator Agent      │
                        │  (LangGraph StateGraph)      │
                        │  routes between agents,      │
                        │  manages state & checkpoints │
                        └──────────┬──────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
              ▼                    ▼                     ▼
  ┌───────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
  │  Resume           │  │  Pre-Screening   │  │  Interview          │
  │  Shortlister      │  │  Call Agent      │  │  Scheduler Agent    │
  │  Agent            │  │                  │  │  (planned)          │
  │                   │  │  • Twilio calls  │  │                     │
  │  • Parses PDF/    │  │  • AI voice      │  │  • Matches slots    │
  │    DOCX resumes   │  │    (Edge TTS)    │  │  • Sends invites    │
  │  • Scores vs JD   │  │  • STT via       │  └─────────────────────┘
  │  • Ranks top 15   │  │    <Gather>      │
  │  • Cohere LLM     │  │  • Collects CTC, │
  └────────┬──────────┘  │    reason,       │
           │             │    availability  │
           ▼             └────────┬─────────┘
  ┌─────────────────┐            │
  │  HITL Gate 1    │            ▼
  │  Recruiter      │   ┌─────────────────┐
  │  approves /     │   │  HITL Gate 2    │
  │  rejects        │   │  Recruiter      │
  │  shortlist      │   │  approves /     │
  └─────────────────┘   │  rejects call   │
                        │  results        │
                        └─────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                   ▼
  ┌───────────────────┐  ┌──────────────┐  ┌──────────────────┐
  │  Background       │  │  Onboarding  │  │  (Future)        │
  │  Verification     │  │  Agent       │  │  Offer Mgmt,     │
  │  Agent (planned)  │  │  (planned)   │  │  Multi-round     │
  │                   │  │              │  │  interviews,     │
  │  • BGV checks     │  │  • Documents │  │  ATS integration │
  │  • Track status   │  │  • Access    │  └──────────────────┘
  └───────────────────┘  │  • Induction │
                         └──────────────┘
```

---

## What's Built and Working Today

### ✅ Resume Shortlister Agent

- Accepts a job description and up to 100 resumes (PDF or DOCX) via REST API
- Extracts full text from each file using `pdfplumber` and `python-docx`
- Sends all resumes + JD to Cohere (`command-r-plus-08-2024`) in a single LLM call
- Returns a ranked shortlist with: candidate name, email, phone, current role, years of experience, skills, match score (out of 10), and a written selection rationale
- Pauses at a HITL gate and waits for the recruiter to approve or reject the shortlist via API

### ✅ Pre-Screening Call Agent

- Dials each approved candidate using a Twilio outbound call
- Runs a live AI voice conversation powered by Edge TTS (Microsoft Neural, free) for speech synthesis and Twilio `<Gather input="speech">` for real-time transcription
- Collects all five pre-screening data points:
  - Is the candidate looking for a change?
  - Reason for change
  - Current CTC
  - Expected CTC
  - Availability / preferred interview slot
- Stores the full call transcript and extracted screening data in MongoDB
- Pauses at a second HITL gate for recruiter review before the pipeline continues

### ✅ End-to-End Run Completed

A real production run was completed:
- Resume: `Sanath_Anantha_Resume_sde.pdf`
- Candidate shortlisted with **9/10** match score
- Live Twilio call placed to `+918951523420`
- Full AI-conducted pre-screening conversation (5+ turns)
- All screening data collected, recruiter approved, workflow completed with status `pre_screening_approved`
- HTML run log generated with overview, full call transcript, and captured terminal logs

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph `StateGraph` with `interrupt_before` HITL gates |
| LLM | Cohere `command-r-plus-08-2024` via `langchain-cohere` |
| Voice calls | Twilio outbound calls + `<Gather input="speech">` for STT |
| Text-to-speech | Edge TTS (Microsoft Neural, free) — served as MP3 from FastAPI `/static` |
| Database | MongoDB (`motor` async driver) + GridFS for file storage |
| API | FastAPI with async lifespan, static file serving |
| Logging | `structlog` JSON logging with per-session JSONL file sink |
| Observability | Latency + token tracking (`tokens_in`, `tokens_out`) on every LLM call |
| Retries | `tenacity` exponential backoff on all external calls |
| Validation | Pydantic v2 settings + request/response schemas |
| Webhook tunneling | `ngrok` for local Twilio webhook delivery |

---

## Project Structure

```
agentic-hr/
├── main.py                    # FastAPI app entry point
├── config/settings.py         # Pydantic settings (reads from .env)
├── core/
│   ├── logging.py             # structlog setup + per-session file log sink
│   ├── observability.py       # @observe_agent, @observe_tool decorators
│   └── exceptions.py          # Custom exceptions + FastAPI error handlers
├── db/mongodb.py              # All MongoDB operations (async / motor)
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
│   └── pre_screener.py        # Call orchestration + result polling node
├── graph/
│   ├── workflow.py            # StateGraph definition + compilation
│   └── edges.py               # Conditional routing after HITL gates
├── hitl/gates.py              # HITL decision handlers (approve / reject)
├── voice/
│   ├── conversation.py        # TwiML state machine for live calls
│   └── tts.py                 # Edge TTS audio generation
├── api/endpoints/
│   ├── workflow.py            # /workflow/* REST endpoints
│   ├── hitl.py                # /hitl/* REST endpoints
│   └── webhooks.py            # /webhooks/twilio/* Twilio callbacks
├── generate_report.py         # HTML run log generator (3-tab report)
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
# Fill in your API keys
```

You need:
- **Cohere API key** — free at [cohere.com](https://cohere.com)
- **Twilio account** — free trial at [twilio.com](https://twilio.com) (verify your phone number in trial mode)
- **MongoDB** — local (`mongodb://localhost:27017`) or Atlas

### 3. Start ngrok

```bash
ngrok http 8000
# Paste the https URL into .env as PUBLIC_BASE_URL
```

Set your Twilio phone number's Voice webhook URL to:
```
https://<your-ngrok-url>/api/webhooks/twilio/voice
```

### 4. Run the server

```bash
python main.py
```

---

## Running the Workflow

### Option A — bash script (recommended)

```bash
bash test_flow.sh /path/to/resume.pdf
```

Walks through the full flow interactively: upload → shortlist review → HITL approve → call → HITL approve → complete.

### Option B — curl

```bash
# 1. Start workflow
curl -X POST http://localhost:8000/api/workflow/start \
  -F "jd_file=@job_description.txt" \
  -F "resume_files=@resume.pdf"

# 2. Check shortlist
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

The report has three tabs — **Overview** (candidate + screening summary), **Call Transcript** (full AI conversation), and **Terminal Logs** (every structlog JSON line captured during the run).

---

## Key Design Decisions

- **LangGraph `interrupt_before`** — HITL gates pause graph execution cleanly without polling or timeouts. `MemorySaver` holds checkpoint state in memory while MongoDB holds business data persistently across restarts.
- **Twilio + Edge TTS** — Twilio handles telephony (STT via `<Gather input="speech">`); Edge TTS generates the AI voice as MP3 served from FastAPI's `/static` endpoint, keeping voice costs at zero.
- **Async-first** — All I/O is async (motor for MongoDB, async FastAPI). Twilio's sync SDK is wrapped with `run_in_executor` to avoid blocking the event loop.
- **TwiML XML escaping** — `&` between query params in TwiML `action` URLs must be escaped as `&amp;`; handled centrally by `_action_url()` in `voice/conversation.py`.
- **Per-session log files** — Every structlog line emitted during a workflow run is written to `logs/<session_id>.jsonl` via a custom processor inserted before `JSONRenderer`. The HTML report reads this file directly, giving you the exact terminal output in the browser.
