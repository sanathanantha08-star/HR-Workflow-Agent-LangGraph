"""
Twilio webhook handlers.

Twilio calls these endpoints during/after outbound calls.
All responses are TwiML (XML).
"""
from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import Response
from typing import Annotated, Optional
from voice.conversation import handle_call_start, handle_speech_input, handle_no_speech
from db import mongodb as db
from core.logging import get_logger

logger = get_logger("api.webhooks")
router = APIRouter(prefix="/webhooks/twilio", tags=["Twilio Webhooks"])

TWIML_CONTENT_TYPE = "application/xml"


@router.post("/ping")
@router.get("/ping")
async def twilio_ping(request: Request):
    """Dead-simple endpoint — use this URL in test_call.py to confirm Twilio can reach us."""
    logger.info("twilio_ping_received", method=request.method)
    return Response(
        content='<?xml version="1.0"?><Response><Say>Hello! The webhook is working.</Say></Response>',
        media_type=TWIML_CONTENT_TYPE,
    )


@router.post("/voice")
async def twilio_voice(
    request: Request,
    session_id: str = Query(...),
    candidate_name: str = Query(...),
    CallSid: Annotated[str, Form()] = "",
    CallStatus: Annotated[str, Form()] = "",
    To: Annotated[str, Form()] = "",
):
    """
    Twilio calls this when the candidate answers.
    Returns TwiML greeting + first <Gather>.
    """
    call_sid = CallSid
    logger.info(
        "twilio_voice_webhook",
        call_sid=call_sid,
        status=CallStatus,
        session_id=session_id,
        candidate=candidate_name,
    )

    twiml = await handle_call_start(call_sid, candidate_name, session_id)
    return Response(content=twiml, media_type=TWIML_CONTENT_TYPE)


@router.post("/gather")
async def twilio_gather(
    request: Request,
    call_sid: str = Query(...),
    session_id: str = Query(...),
    candidate_name: str = Query(...),
    SpeechResult: Annotated[Optional[str], Form()] = None,
    Confidence: Annotated[Optional[str], Form()] = None,
):
    """
    Twilio sends the speech transcript here after <Gather input="speech">.
    """
    logger.info(
        "twilio_gather_webhook",
        call_sid=call_sid,
        session_id=session_id,
        speech=SpeechResult,
        confidence=Confidence,
    )

    if not SpeechResult:
        twiml = await handle_no_speech(call_sid, candidate_name, session_id, retries=0)
    else:
        twiml = await handle_speech_input(call_sid, candidate_name, session_id, SpeechResult)

    return Response(content=twiml, media_type=TWIML_CONTENT_TYPE)


@router.post("/no-speech")
async def twilio_no_speech(
    request: Request,
    call_sid: str = Query(...),
    session_id: str = Query(...),
    candidate_name: str = Query(...),
    retries: int = Query(default=0),
):
    """Called when <Gather> redirect fires with no speech input."""
    logger.info("twilio_no_speech", call_sid=call_sid, session_id=session_id, retries=retries)
    twiml = await handle_no_speech(call_sid, candidate_name, session_id, retries=retries)
    return Response(content=twiml, media_type=TWIML_CONTENT_TYPE)


@router.post("/call-status")
async def twilio_call_status(
    request: Request,
    CallSid: Annotated[str, Form()] = "",
    CallStatus: Annotated[str, Form()] = "",
    CallDuration: Annotated[Optional[str], Form()] = None,
):
    """Twilio status callback — updates call record in MongoDB."""
    logger.info(
        "twilio_call_status",
        call_sid=CallSid,
        status=CallStatus,
        duration=CallDuration,
    )

    terminal_statuses = {"completed", "failed", "busy", "no-answer", "canceled"}
    update: dict = {"status": CallStatus}
    if CallDuration:
        update["duration_seconds"] = int(CallDuration)

    if CallStatus in terminal_statuses:
        call_doc = await db.get_call_record(CallSid)
        if call_doc and call_doc.get("status") not in ("completed", "failed"):
            # Only mark failed if call didn't complete a full conversation
            if CallStatus != "completed":
                update["status"] = CallStatus
            await db.update_call_record(CallSid, update)
    else:
        await db.update_call_record(CallSid, update)

    return Response(content="<?xml version='1.0'?><Response/>", media_type=TWIML_CONTENT_TYPE)
