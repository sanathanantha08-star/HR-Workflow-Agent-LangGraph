"""
Voice conversation state machine for pre-screening calls.
"""
import asyncio
from functools import partial
from urllib.parse import quote, urlencode
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


def _action_url(path: str, **params) -> str:
    """Build a webhook URL and XML-escape the & between query params."""
    qs = urlencode(params)
    return f"{_settings.public_base_url}{path}?{qs}".replace("&", "&amp;")


def _xml_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def handle_call_start(call_sid: str, candidate_name: str, session_id: str) -> str:
    greeting = GREETING_TEMPLATE.format(name=candidate_name, company="our company")

    await db.append_call_turn(call_sid, "agent", greeting)
    await db.update_call_record(call_sid, {"status": "in_progress"})
    logger.info("call_start", call_sid=call_sid, candidate=candidate_name)

    gather_url   = _action_url("/api/webhooks/twilio/gather",    call_sid=call_sid, session_id=session_id, candidate_name=candidate_name)
    no_input_url = _action_url("/api/webhooks/twilio/no-speech", call_sid=call_sid, session_id=session_id, candidate_name=candidate_name, retries=0)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Gather input="speech" action="{gather_url}" method="POST" speechTimeout="auto" timeout="15" actionOnEmptyResult="true">'
        f'<Say voice="alice">{_xml_text(greeting)}</Say>'
        "</Gather>"
        f'<Redirect method="POST">{no_input_url}</Redirect>'
        "</Response>"
    )


async def handle_speech_input(
    call_sid: str,
    candidate_name: str,
    session_id: str,
    speech_result: str,
) -> str:
    logger.info("speech_input", call_sid=call_sid, text=speech_result[:100])

    await db.append_call_turn(call_sid, "candidate", speech_result)

    call_doc = await db.get_call_record(call_sid)
    if not call_doc:
        return _hangup_twiml("Thank you. Goodbye!")

    conversation    = call_doc.get("conversation", [])
    screening_data  = call_doc.get("screening_data", {})

    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            llm_generate_call_response,
            candidate_name=candidate_name,
            conversation_history=conversation,
            screening_data=screening_data,
        ),
    )

    reply: str          = result.get("reply", "Thank you for your time. Goodbye!")
    is_complete: bool   = result.get("is_complete", False)
    updated_screening   = result.get("screening_data", {})

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


MAX_NO_SPEECH_RETRIES = 2

async def handle_no_speech(
    call_sid: str, candidate_name: str, session_id: str, retries: int = 0
) -> str:
    logger.info("no_speech_detected", call_sid=call_sid, retries=retries)

    if retries < MAX_NO_SPEECH_RETRIES:
        # Retry: ask the candidate to speak again
        prompt = "I'm sorry, I didn't catch that. Could you please say that again?"
        gather_url   = _action_url("/api/webhooks/twilio/gather",    call_sid=call_sid, session_id=session_id, candidate_name=candidate_name)
        no_input_url = _action_url("/api/webhooks/twilio/no-speech", call_sid=call_sid, session_id=session_id, candidate_name=candidate_name, retries=retries + 1)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            f'<Gather input="speech" action="{gather_url}" method="POST" speechTimeout="auto" timeout="15" actionOnEmptyResult="true">'
            f'<Say voice="alice">{_xml_text(prompt)}</Say>'
            "</Gather>"
            f'<Redirect method="POST">{no_input_url}</Redirect>'
            "</Response>"
        )

    # Max retries exhausted — hang up
    logger.info("no_speech_max_retries", call_sid=call_sid)
    await db.update_call_record(call_sid, {"status": "no_answer"})
    return _hangup_twiml("I'm sorry, I'm having trouble hearing you. I'll try reaching out again. Goodbye!")


async def _build_gather_twiml(text: str, call_sid: str, session_id: str, candidate_name: str) -> str:
    gather_url   = _action_url("/api/webhooks/twilio/gather",    call_sid=call_sid, session_id=session_id, candidate_name=candidate_name)
    no_input_url = _action_url("/api/webhooks/twilio/no-speech", call_sid=call_sid, session_id=session_id, candidate_name=candidate_name, retries=0)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Gather input="speech" action="{gather_url}" method="POST" speechTimeout="auto" timeout="10" actionOnEmptyResult="true">'
        f'<Say voice="alice">{_xml_text(text)}</Say>'
        "</Gather>"
        f'<Redirect method="POST">{no_input_url}</Redirect>'
        "</Response>"
    )


def _hangup_twiml(text: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Say voice="alice">{_xml_text(text)}</Say>'
        "<Hangup/>"
        "</Response>"
    )
