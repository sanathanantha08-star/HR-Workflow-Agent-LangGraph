from urllib.parse import quote
from twilio.rest import Client as TwilioClient
from config.settings import get_settings
from core.logging import get_logger
from core.exceptions import CallError
from tools.base import tool_call, with_retry

logger = get_logger("tools.call")
_settings = get_settings()

_twilio_client: TwilioClient | None = None


def get_twilio_client() -> TwilioClient:
    global _twilio_client
    if _twilio_client is None:
        if not _settings.twilio_account_sid or not _settings.twilio_auth_token:
            raise CallError(
                "Twilio credentials not configured",
                details={"hint": "Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env"},
            )
        _twilio_client = TwilioClient(
            _settings.twilio_account_sid, _settings.twilio_auth_token
        )
        logger.info("twilio_client_initialized")
    return _twilio_client


@tool_call("initiate_outbound_call")
@with_retry(reraise_on=(Exception,))
def initiate_outbound_call(to_phone: str, candidate_name: str, session_id: str) -> dict:
    """
    Initiate an outbound call via Twilio.
    Returns {call_sid, status}.
    """
    client = get_twilio_client()
    # Normalize to E.164: strip spaces, dashes, parens (Twilio requires +918951523420 not +91 8951523420)
    to_phone = "".join(c for c in to_phone if c.isdigit() or c == "+")
    webhook_url = (
        f"{_settings.public_base_url}/api/webhooks/twilio/voice"
        f"?session_id={quote(session_id)}&candidate_name={quote(candidate_name)}"
    )
    status_callback = f"{_settings.public_base_url}/api/webhooks/twilio/call-status"

    try:
        call = client.calls.create(
            to=to_phone,
            from_=_settings.twilio_from_number,
            url=webhook_url,
            status_callback=status_callback,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
        )
        logger.info(
            "call_initiated",
            call_sid=call.sid,
            to=to_phone,
            candidate=candidate_name,
            session_id=session_id,
        )
        return {"call_sid": call.sid, "status": call.status}
    except Exception as exc:
        raise CallError(f"Failed to initiate call to {to_phone}: {exc}") from exc


@tool_call("get_call_status")
@with_retry(reraise_on=(Exception,))
def get_call_status(call_sid: str) -> dict:
    """Fetch call status from Twilio API."""
    try:
        call = get_twilio_client().calls(call_sid).fetch()
        logger.info("call_status_fetched", call_sid=call_sid, status=call.status)
        return {"call_sid": call_sid, "status": call.status, "duration": call.duration}
    except Exception as exc:
        raise CallError(f"Failed to fetch call status for {call_sid}: {exc}") from exc
