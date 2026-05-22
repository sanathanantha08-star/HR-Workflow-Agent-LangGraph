"""
Voice conversation state machine for pre-screening calls.

Twilio flow:
  1. Call answered → /api/webhooks/twilio/voice returns TwiML with greeting.
  2. <Gather input="speech"> sends transcript to /api/webhooks/twilio/gather.
  3. We call Cohere to generate next response.
  4. We use Edge TTS to generate audio and respond with <Play> + <Gather>.
  5. Repeat until is_complete=True, then hang up and save screening data.
"""
from tools.llm_tools import llm_generate_call_response
from voice.tts import get_audio_url
from db import mongodb as db
from config.settings import get_settings
from core.logging import get_logger

logger = get_logger("voice.conversation")
_settings = get_settings()


GREETING_TEMPLATE = (
    "Hello, may I speak with {name}? "
    "I'm calling on behalf of {company} regarding a job opportunity. "
    "This is a quick pre-screening call. Is this a good time to chat?"
)


async def handle_call_start(call_sid: str, candidate_name: str, session_id: str) -> str:
    """
    Called when a candidate answers. Returns TwiML to greet and gather first response.
    """
    greeting = GREETING_TEMPLATE.format(name=candidate_name, company="our company")

    await db.append_call_turn(call_sid, "agent", greeting)
    await db.update_call_record(call_sid, {"status": "in_progress"})

    logger.info("call_start", call_sid=call_sid, candidate=candidate_name)
    return await _build_gather_twiml(greeting, call_sid, session_id, candidate_name)


async def handle_speech_input(
    call_sid: str,
    candidate_name: str,
    session_id: str,
    speech_result: str,
) -> str:
    """
    Called when candidate speaks. Generates next agent response.
    Returns TwiML with next <Play>/<Gather> or <Hangup>.
    """
    logger.info("speech_input", call_sid=call_sid, text=speech_result[:100])

    await db.append_call_turn(call_sid, "candidate", speech_result)

    call_doc = await db.get_call_record(call_sid)
    if not call_doc:
        return _hangup_twiml("Thank you. Goodbye!")

    conversation = call_doc.get("conversation", [])
    screening_data = call_doc.get("screening_data", {})

    # Generate next response via Cohere
    result = llm_generate_call_response(
        candidate_name=candidate_name,
        conversation_history=conversation,
        screening_data=screening_data,
    )

    reply: str = result.get("reply", "Thank you for your time. Goodbye!")
    is_complete: bool = result.get("is_complete", False)
    updated_screening: dict = result.get("screening_data", {})

    await db.append_call_turn(call_sid, "agent", reply)
    await db.update_call_record(call_sid, {"screening_data": updated_screening})

    logger.info(
        "agent_reply_generated",
        call_sid=call_sid,
        is_complete=is_complete,
        tokens_in=result.get("tokens_in"),
        tokens_out=result.get("tokens_out"),
    )

    if is_complete:
        await db.update_call_record(call_sid, {"status": "completed", "screening_data": updated_screening})
        return _hangup_twiml(reply)

    return await _build_gather_twiml(reply, call_sid, session_id, candidate_name)


async def handle_no_speech(call_sid: str, candidate_name: str, session_id: str) -> str:
    """Called when <Gather> times out with no speech input."""
    logger.info("no_speech_detected", call_sid=call_sid)
    await db.update_call_record(call_sid, {"status": "no_answer"})
    fallback = "I'm sorry, I couldn't hear you. I'll try reaching out again. Goodbye!"
    return _hangup_twiml(fallback)


async def _build_gather_twiml(
    text: str, call_sid: str, session_id: str, candidate_name: str
) -> str:
    """Build TwiML with <Play> (Edge TTS audio) and <Gather input='speech'>."""
    audio_url = await get_audio_url(text, _settings.public_base_url)
    gather_action = (
        f"{_settings.public_base_url}/api/webhooks/twilio/gather"
        f"?call_sid={call_sid}&session_id={session_id}&candidate_name={candidate_name}"
    )
    no_speech_action = (
        f"{_settings.public_base_url}/api/webhooks/twilio/no-speech"
        f"?call_sid={call_sid}&session_id={session_id}&candidate_name={candidate_name}"
    )

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="{gather_action}" method="POST"
          speechTimeout="3" timeout="10" actionOnEmptyResult="true">
    <Play>{audio_url}</Play>
  </Gather>
  <Redirect method="POST">{no_speech_action}</Redirect>
</Response>"""
    return twiml


def _hangup_twiml(text: str) -> str:
    """TwiML that says text via <Say> and hangs up."""
    safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna">{safe_text}</Say>
  <Hangup/>
</Response>"""
