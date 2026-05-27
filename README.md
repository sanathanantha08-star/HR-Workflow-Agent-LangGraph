## 🎥 Demo Video

<a href="https://drive.google.com/file/d/1roehN6HuL5tVceFOhKQbtvFFYiv2vE6T/view?usp=drive_link" target="_blank">Watch Full Demo Video</a>

# Agentic HR — AI-Powered Recruitment Pipeline

An end-to-end autonomous recruitment pipeline built with multi-agent AI. The system replaces repetitive HR coordination tasks with a chain of specialised AI agents, each handling one stage of the hiring process — while keeping humans in control at every decision point through built-in approval gates.

---

## What This Project Does

A recruiter uploads a job description and a batch of resumes. From that moment, a multi-agent pipeline takes over:

1. **Orchestrator Agent** receives the trigger and coordinates the entire pipeline, routing work between specialised agents and surfacing decisions to the recruiter when human judgment is needed.

2. **Resume Shortlister Agent** reads every resume, scores each candidate against the job description, and produces a ranked shortlist with a match score and selection rationale for each. The shortlist is sent to the recruiter for approval (HITL Gate 1).

3. **Pre-Screening Call Agent** — after the recruiter approves the shortlist — calls each shortlisted candidate over the phone using a live AI voice agent. It conducts a natural conversation and collects: job change intent, reason for change, current CTC, expected CTC, and availability for an interview slot. The collected data is sent back to the recruiter for approval (HITL Gate 2).

4. **Interview Scheduler Agent** takes the approved pre-screening results, checks the recruiter's Google Calendar for availability, finds the first free 1-hour block within the candidate's declared window, creates a Google Calendar event with a Google Meet link, and sends professional confirmation emails to both the candidate and the recruiter.

5. **Onboarding Agent** — after interviews are conducted — presents HR with a list of all interviewed candidates and lets them select who cleared the round. For every selected candidate, a personalised congratulations + onboarding email is sent automatically, welcoming them to the team and outlining next steps (offer letter, document collection, joining date confirmation). This stage has its own HITL Gate 3.

6. **Background Verification Agent** *(backlog)* — will initiate and track BGV checks once the interview stage is cleared.

> The architecture is built to be extended: offer management, document collection, multiple interview rounds, ATS integrations, and per-company workflow configuration are all on the roadmap.

---

## Architecture

```
                        ┌─────────────────────────────────┐
                        │         RECRUITER / HR           │
                        │  (uploads JD + resumes, reviews  │
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
  │  Agent            │  │                  │  │                     │
  │                   │  │  • Twilio calls  │  │  • Checks Google    │
  │  • Parses PDF/    │  │  • AI voice      │  │    Calendar (OAuth) │
  │    DOCX resumes   │  │    (Edge TTS)    │  │  • Finds free 1-hr  │
  │  • Scores vs JD   │  │  • STT via       │  │    block in window  │
  │  • Ranks top 15   │  │    <Gather>      │  │  • Creates event +  │
  │  • Groq LLM       │  │  • Collects CTC, │  │    Google Meet link │
  └────────┬──────────┘  │    reason,       │  │  • Sends emails via │
           │             │    availability  │  │    Gmail API        │
           ▼             └────────┬─────────┘  └──────────┬──────────┘
  ┌─────────────────┐            │                        │
  │  HITL Gate 1    │            ▼                        ▼
  │  Recruiter      │   ┌─────────────────┐     ┌─────────────────┐
  │  approves /     │   │  HITL Gate 2    │     │  HITL Gate 3    │
  │  rejects        │   │  Recruiter      │     │  HR selects     │
  │  shortlist      │   │  approves /     │     │  cleared        │
  └─────────────────┘   │  rejects call   │     │  candidates     │
                        │  results        │     └────────┬────────┘
                        └─────────────────┘              │
                                                         ▼
                                               ┌─────────────────────┐
                                               │  Onboarding Agent   │
                                               │                     │
                                               │  • Sends congrats   │
                                               │    + onboarding     │
                                               │    email to each    │
                                               │    selected         │
                                               │    candidate        │
                                               └─────────────────────┘
```

---

## Demo Screenshots

The screenshots below follow a real end-to-end run in sequence — from uploading files to workflow completion, including the clickable step-history drawers and the HTML run log.

**1. Upload screen — clean landing page, drop zones for JD and resumes**
![Upload screen empty](public/images/1.png)

**2. Files selected — JD and 3 candidate resumes ready to launch**
![Files selected and ready](public/images/2.png)

**3. Resume Parser agent active — pipeline nodes light up, parsing in progress**
![Resume Parser agent working](public/images/4.png)

**4. HITL Gate 1 — shortlisted candidates with match scores, awaiting recruiter approval**
![Shortlist review](public/images/3.png)

**5. Pre-Screening Calls — AI voice agent calling candidates sequentially (1 of 2 done)**
![Pre-screening calls in progress](public/images/5.png)

**6. HITL Gate 2 — pre-screening results collected, recruiter reviews before completing**
![Pre-screening results review](public/images/6.png)

**7. Workflow Complete — all pipeline nodes green, run log ready to open**
![Workflow complete](public/images/7.png)

**8. HTML Run Log — Overview tab with candidate summary, screening data, and workflow timeline**
![Run log overview tab](public/images/8.png)

**9. HTML Run Log — Call Transcript tab showing the full AI-conducted conversation**
![Run log call transcript](public/images/9.png)

**10. Step history drawer — clicking a done node shows Resume Analysis data inline**
![Resume analysis drawer](public/images/10.png)

**11. Step history drawer — Shortlist Approval decision and AI rationale**
![Shortlist approval drawer](public/images/11.png)

**12. Step history drawer — Pre-Screening Calls results for all candidates**
![Pre-screening calls drawer](public/images/12.png)

**13. Complete Run log**
![Complete run log](public/images/13.png)

**14. HITL Gate 2 (Final Review) — Pre-screening results displayed with candidate's CTC, experience, reason for change, and declared interview slots.**
![Final review HITL gate with pre-screening data](public/images/14.png)

**15. Interview Scheduler Agent active — agent checks the recruiter's Google Calendar for available 1-hour slots.**
![Interview scheduler agent running](public/images/15.png)

**16. Workflow Complete — all pipeline nodes green. Interview scheduled and confirmation emails dispatched.**
![Full workflow complete with interview scheduled](public/images/16.png)

**17. Candidate's inbox — professional Round 1 interview confirmation email with date, time, duration, mode, and live meeting link.**
![Candidate interview confirmation email](public/images/17.png)

**18. Candidate's inbox — Google Calendar invite received for the interview.**
![Recruiter Google Calendar invite email](public/images/18.png)

**19. Recruiter's Google Calendar — 1-hour interview event created automatically with the Google Meet link attached.**
![Interview event on recruiter Google Calendar](public/images/19.png)

**20.HR Selects the candidates who have positive Feedback and can be onboarded**
![Interview event on recruiter Google Calendar](public/images/20.png)

**21.Onboarding Agent in Action**
![Interview event on recruiter Google Calendar](public/images/21.png)
**22.Onboarding Agent in Action**
![Interview event on recruiter Google Calendar](public/images/22.png)
**23.Onboarded candidates recieve the Welcome Mail**
![Interview event on recruiter Google Calendar](public/images/23.png)

---

## Changelog

### 27 May 2026 — Onboarding Agent & HITL Gate 3

**New: Onboarding Agent** (`agents/onboarding_agent.py`)

After interviews are scheduled, a new HITL Gate 3 presents HR with a checkbox list of all interviewed candidates. HR selects who cleared the round and clicks "Send Onboarding Emails". The Onboarding Agent sends a personalised congratulations email to each selected candidate welcoming them to the team and outlining next steps (offer letter timeline, document checklist, joining date confirmation).

- Added `OnboardingAgent` class in `agents/onboarding_agent.py`
- Added `send_onboarding_email()` to `tools/email_tools.py` — casual, emoji-friendly congratulations email template
- Added `hitl_onboarding_node` and `onboarding_node` to `graph/nodes.py`
- Added `route_after_onboarding_hitl` edge to `graph/edges.py`
- Wired `email_interview_scheduler → hitl_onboarding → onboarding → END` in `graph/workflow.py`; `hitl_onboarding` added to `interrupt_before`
- Added `onboarding_approval_status`, `onboarding_selected_ids`, `onboarding_results` fields to `models/state.py`
- Added `POST /api/hitl/{session_id}/onboarding` endpoint (`api/endpoints/hitl.py`) accepting `{ selected_candidate_ids: [...] }`
- Added `OnboardingDecisionRequest` schema and updated `WorkflowStatusResponse` with onboarding fields (`models/schemas.py`)
- Frontend: 8th pipeline node "Onboarding" (🎉, HITL type) added; dedicated `onboarding_active` view with its own pipeline state so the Onboarding node lights up during email sending (not Interview Scheduler)
- Added `POST /api/debug/skip-to-onboarding` debug endpoint (`api/endpoints/debug.py`) — injects mock scheduling results and fast-forwards the graph to the onboarding gate for isolated testing

---

### 26 May 2026 — Email Interview Scheduler Agent

**New: Email Interview Scheduler Agent** (`agents/email_interview_scheduler.py`)

- Integrated the Email Agent into the pipeline as the 6th node
- Agent reads pre-screening results, checks Google Calendar for free 1-hour slots, creates calendar events with Google Meet links, and sends confirmation emails
- Updated frontend pipeline strip to show 7 nodes (added Interview Scheduler)
- Added support for multiple workflow runs per session in the UI

---

### 23 May 2026 — Interview Scheduler Agent, Google Calendar & Gmail Integration

**New: Interview Scheduler Agent** (`agents/email_interview_scheduler.py`)

Built from scratch to handle the interview scheduling stage. Previously listed as "planned"; now fully operational.

- Receives pre-screened candidates with declared availability windows from graph state after HITL Gate 2 approval
- Iterates through availability windows in **1-hour increments** using `check_slot_free()` to query the recruiter's Google Calendar
- Books the first free 1-hour block via `create_calendar_event()`, generating a Google Meet link automatically
- Dispatches `send_interview_emails()` confirmation to both candidate and recruiter

**New: Google Calendar Integration** (`tools/calendar_tools.py`)

- `check_slot_free(start_dt, end_dt)` — queries recruiter's calendar via Freebusy API; falls back to `True` in demo environments without credentials
- `create_calendar_event(...)` — creates event with both parties as attendees, auto-generates Google Meet link via `conferenceData` + `conferenceDataVersion=1`

**New: Gmail API Integration** (`tools/email_tools.py`)

- Replaced SMTP approach with Gmail API (OAuth2, `gmail.send` scope)
- Same `google_token.json` covers both Calendar and Gmail — no credential sprawl
- Professional email templates with formatted interview details block for candidate and recruiter

**Other changes on this date:**
- Dedicated HR agent email account set up (`hragentdonotreply@gmail.com`) — later changed to `sanath.anantha08@gmail.com`
- Recruiter's Google Calendar configured to share "Make changes to events" access with agent account
- Graph wired: `hitl_pre_screening → email_interview_scheduler → END`
- `setup_google_auth.py` added for one-time OAuth2 token generation

---

### 22 May 2026 — Pre-Screening Call Agent

**New: Pre-Screening Call Agent** (`agents/pre_screener.py`)

- Dials each approved candidate via Twilio outbound call
- AI voice conversation powered by Edge TTS (Microsoft Neural) for speech synthesis and Twilio `<Gather input="speech">` for real-time STT
- Collects all five screening data points: job change intent, reason for change, current CTC, expected CTC, interview availability
- Full call transcript and extracted screening data stored in MongoDB
- HITL Gate 2 added for recruiter review

---

### 21 May 2026 — Resume Shortlister Agent & Initial Pipeline

**Initial build: Core pipeline**

- `Resume Shortlister Agent` — parses PDF/DOCX resumes, scores against JD via Groq LLM, returns ranked shortlist with match scores and rationale
- LangGraph `StateGraph` with `interrupt_before` HITL gates
- FastAPI backend, MongoDB storage, Pydantic schemas
- HITL Gate 1 — recruiter approves or rejects shortlist with optional feedback (triggers re-run on rejection)
- Single-page frontend with pipeline strip visualization

---

## Backlog

| ID | Title | Type | Priority | Status | Description |
|----|-------|------|----------|--------|-------------|
| BL-001 | Production-Ready Voice Agent | Enhancement | High | Planned | Current implementation uses Edge TTS + Twilio `<Gather>`, which buffers the entire audio response before playing — causing 3–5s latency per turn and making calls feel unnatural. Replace with a production-grade voice platform (Vapi, Bolna, or similar) that: streams TTS chunks as they are generated rather than waiting for the full response; handles interruptions and barge-in; natively detects silence and disfluencies (ah, uhm, err) without custom logic; provides call analytics and transcription out of the box. Bolna is preferred for India deployments (Plivo backend, avoids TRAI DND blocks on US numbers). |
| BL-002 | Background Verification (BGV) Agent | New Feature | Medium | Planned | Add a BGV Agent node after the onboarding stage. The agent should initiate BGV checks with a third-party provider (e.g., SpringVerify, AuthBridge) for each onboarded candidate, poll for status updates, and surface results to HR via a new HITL gate. Should cover identity, education, and employment history checks at minimum. |
| BL-003 | Document Collection & Onboarding Formalities Agent | New Feature | Medium | Planned | Extend the Onboarding Agent scope with a dedicated Document Agent that handles post-offer paperwork: sends a document checklist to the candidate (ID proof, educational certificates, previous employment letters, etc.), tracks submission status, and notifies HR when all documents are received. Ideally implemented as an extension of the existing Onboarding Agent with additional state fields and a document-tracking HITL gate. Ties in with BL-002 for BGV document reuse. |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph `StateGraph` with `interrupt_before` HITL gates |
| LLM | Groq (`llama-3.3-70b-versatile`) via `langchain-groq` |
| Voice calls | Twilio outbound calls + `<Gather input="speech">` for STT |
| Text-to-speech | Edge TTS (Microsoft Neural, free) — served as MP3 from FastAPI `/static` |
| Calendar integration | Google Calendar API v3 (Freebusy + Events insert with Google Meet) |
| Email sending | Gmail API v1 (OAuth2, `gmail.send` scope) — no SMTP or App Passwords |
| Video conferencing | Google Meet — auto-generated via `conferenceData` on Calendar event creation |
| Google Auth | OAuth2 via `google-auth-oauthlib`; token stored in `google_token.json`, auto-refreshed |
| Database | MongoDB (`motor` async driver) + GridFS for file storage |
| API | FastAPI with async lifespan, static file serving |
| Logging | `structlog` JSON logging with per-session JSONL file sink |
| Observability | Latency + token tracking (`tokens_in`, `tokens_out`) on every LLM call |
| Retries | `tenacity` exponential backoff on all external calls |
| Validation | Pydantic v2 settings + request/response schemas |
| Webhook tunneling | Cloudflare Tunnel for local Twilio webhook delivery |

---

## Project Structure

```
agentic-hr/
├── main.py                              # FastAPI app entry point
├── config/settings.py                   # Pydantic settings (reads from .env)
├── core/
│   ├── logging.py                       # structlog setup + per-session file log sink
│   ├── observability.py                 # @observe_agent, @observe_tool decorators
│   └── exceptions.py                    # Custom exceptions + FastAPI error handlers
├── db/mongodb.py                        # All MongoDB operations (async / motor)
├── models/
│   ├── state.py                         # LangGraph HRWorkflowState TypedDict
│   └── schemas.py                       # Pydantic request/response schemas
├── tools/
│   ├── base.py                          # @tool_call, @with_retry decorators
│   ├── file_tools.py                    # PDF/DOCX text extraction
│   ├── llm_tools.py                     # Groq LLM wrappers
│   ├── call_tools.py                    # Twilio outbound call initiator
│   ├── calendar_tools.py                # Google Calendar freebusy + event creation
│   └── email_tools.py                   # Gmail API — interview + onboarding emails
├── agents/
│   ├── base.py                          # BaseAgent with arun() + metric logging
│   ├── resume_shortlister.py            # Resume parsing + LLM ranking node
│   ├── pre_screener.py                  # Call orchestration + result polling node
│   ├── email_interview_scheduler.py     # Interview slot finder + email dispatcher
│   └── onboarding_agent.py              # Congratulations email sender (HITL Gate 3)
├── graph/
│   ├── workflow.py                      # StateGraph definition + compilation
│   ├── nodes.py                         # All LangGraph node functions
│   └── edges.py                         # Conditional routing after HITL gates
├── hitl/gates.py                        # HITL decision handlers (approve / reject / onboard)
├── voice/
│   ├── conversation.py                  # TwiML state machine for live calls
│   └── tts.py                           # Edge TTS audio generation
├── api/
│   ├── router.py                        # API router registration
│   └── endpoints/
│       ├── workflow.py                  # /workflow/* REST endpoints
│       ├── hitl.py                      # /hitl/* REST endpoints (shortlist, pre-screening, onboarding)
│       ├── webhooks.py                  # /webhooks/twilio/* Twilio callbacks
│       └── debug.py                     # /debug/* dev-only endpoints (skip-to-onboarding)
├── setup_google_auth.py                 # One-time OAuth2 setup for Google APIs
├── google_credentials.json              # OAuth client ID + secret from Google Cloud Console
├── google_token.json                    # OAuth access + refresh token (generated by setup script)
├── generate_report.py                   # HTML run log generator (3-tab report)
├── .env.example                         # Environment variable template
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
- **Groq API key** — free at [console.groq.com](https://console.groq.com)
- **Twilio account** — free trial at [twilio.com](https://twilio.com) (verify your phone number in trial mode)
- **MongoDB** — local (`mongodb://localhost:27017`) or Atlas
- **Google Cloud project** — with Gmail API and Google Calendar API enabled; OAuth client ID downloaded as `google_credentials.json`

### 3. Set up Google OAuth (one-time)

```bash
# Run this once, sign in as sanath.anantha08@gmail.com when the browser opens
python setup_google_auth.py
```

This generates `google_token.json`. Set `GOOGLE_TOKEN_PATH=./google_token.json` in `.env`.

The recruiter's calendar must share **"Make changes to events"** access with `sanath.anantha08@gmail.com` via Google Calendar Settings.

### 4. Start Cloudflare Tunnel

```bash
cloudflared tunnel --url http://localhost:8000
# Paste the https URL into .env as PUBLIC_BASE_URL
```

Set your Twilio phone number's Voice webhook URL to:
```
https://<your-tunnel-url>/api/webhooks/twilio/voice
```

### 5. Run the server

```bash
python main.py
```

---

## Running the Workflow

### Option A — Web UI (recommended)

Open `http://localhost:8000`, upload JD + resumes, and follow the pipeline visually. Use the **"🛠 Debug: Skip to Onboarding"** button on the upload screen to test the onboarding flow in isolation without running calls or the email scheduler.

### Option B — curl

```bash
# 1. Start workflow
curl -X POST http://localhost:8000/api/workflow/start \
  -F "jd_file=@job_description.txt" \
  -F "resume_files=@resume.pdf"

# 2. Approve shortlist
curl -X POST http://localhost:8000/api/hitl/<session_id>/shortlist \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "feedback": "Looks good"}'

# 3. Approve pre-screening (triggers interview scheduling automatically)
curl -X POST http://localhost:8000/api/hitl/<session_id>/pre-screening \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved", "feedback": "Ready for interview"}'

# 4. Submit onboarding selection
curl -X POST http://localhost:8000/api/hitl/<session_id>/onboarding \
  -H "Content-Type: application/json" \
  -d '{"selected_candidate_ids": ["cand_001", "cand_002"]}'
```

### Generating the HTML Run Log

```bash
python generate_report.py <session_id>
open run_log_<first8chars>.html
```

---

## Key Design Decisions

- **LangGraph `interrupt_before`** — HITL gates pause graph execution cleanly without polling or timeouts. `MemorySaver` holds checkpoint state in memory while MongoDB holds business data persistently across restarts.
- **Twilio + Edge TTS** — Twilio handles telephony (STT via `<Gather input="speech">`); Edge TTS generates the AI voice as MP3 served from FastAPI's `/static` endpoint, keeping voice costs at zero. See BL-001 for the planned upgrade to a production-grade streaming voice platform.
- **1-hour block scanning** — Rather than booking the candidate's entire declared window, the scheduler slides a 1-hour window across the availability range and picks the first slot where the recruiter's calendar is free.
- **Google Meet via `conferenceData`** — Passing `conferenceData` with `conferenceSolutionKey: {type: "hangoutsMeet"}` and `conferenceDataVersion=1` to the Calendar Events insert API auto-generates a Meet link without any additional API calls.
- **Single OAuth token for calendar + email** — Both the Google Calendar API and Gmail API share the same `google_token.json` issued with `calendar` + `gmail.send` scopes in one OAuth flow.
- **Async-first** — All I/O is async (motor for MongoDB, async FastAPI). Twilio's sync SDK and Google's sync client libraries are wrapped with `run_in_executor` to avoid blocking the event loop.
- **Per-session log files** — Every structlog line emitted during a workflow run is written to `logs/<session_id>.jsonl` via a custom processor. The HTML report reads this file directly.
