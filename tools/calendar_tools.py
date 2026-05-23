"""
Google Calendar integration for checking recruiter availability and creating events.
Uses OAuth2 credentials stored in a JSON token file (GOOGLE_TOKEN_PATH env var).
If credentials are not configured, assumes all slots are free (demo fallback).
"""
import datetime
import json
import os
from typing import Optional
from config.settings import get_settings
from core.logging import get_logger

logger = get_logger("tools.calendar")

RECRUITER_CALENDAR_ID = "sanath.anantha07@gmail.com"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]


def _get_calendar_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    settings = get_settings()
    token_path = settings.google_token_path

    if not token_path or not os.path.exists(token_path):
        raise RuntimeError(
            f"Google token file not found at '{token_path}'. "
            "Run the OAuth2 setup flow to generate it."
        )

    with open(token_path) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes", SCOPES),
    )

    # Auto-refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_data.update({
            "token": creds.token,
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
        })
        with open(token_path, "w") as f:
            json.dump(token_data, f)

    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def check_slot_free(start_dt: datetime.datetime, end_dt: datetime.datetime) -> bool:
    """
    Return True if the recruiter's calendar has no events in [start_dt, end_dt].
    Falls back to True (assume free) if Google credentials are not configured.
    """
    settings = get_settings()
    if not settings.google_token_path:
        logger.warning("google_calendar_not_configured_assuming_free")
        return True

    try:
        service = _get_calendar_service()
        body = {
            "timeMin": start_dt.isoformat(),
            "timeMax": end_dt.isoformat(),
            "items": [{"id": RECRUITER_CALENDAR_ID}],
        }
        result = service.freebusy().query(body=body).execute()
        busy = (
            result.get("calendars", {})
            .get(RECRUITER_CALENDAR_ID, {})
            .get("busy", [])
        )
        is_free = len(busy) == 0
        logger.info(
            "calendar_slot_checked",
            start=start_dt.isoformat(),
            end=end_dt.isoformat(),
            is_free=is_free,
            busy_count=len(busy),
        )
        return is_free
    except Exception as exc:
        logger.error("calendar_check_failed", error=str(exc))
        return False  # treat errors as busy to avoid double-booking


def create_calendar_event(
    candidate_name: str,
    candidate_email: str,
    start_dt: datetime.datetime,
    end_dt: datetime.datetime,
) -> str:
    """
    Create a Google Calendar event on the recruiter's calendar.
    Returns the event's HTML link, or empty string on failure.
    """
    settings = get_settings()
    if not settings.google_token_path:
        logger.warning("google_calendar_not_configured_skipping_event_creation")
        return ""

    try:
        service = _get_calendar_service()
        event_body = {
            "summary": f"Interview: {candidate_name}",
            "description": (
                f"Pre-screened candidate interview.\n"
                f"Candidate: {candidate_name}\n"
                f"Email: {candidate_email}"
            ),
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "attendees": [
                {"email": RECRUITER_CALENDAR_ID},
                {"email": candidate_email},
            ],
            "conferenceData": {
                "createRequest": {
                    "requestId": f"interview-{candidate_name.replace(' ', '-').lower()}-{start_dt.strftime('%Y%m%d%H%M')}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "reminders": {"useDefault": True},
        }
        created = (
            service.events()
            .insert(
                calendarId=RECRUITER_CALENDAR_ID,
                body=event_body,
                sendUpdates="all",
                conferenceDataVersion=1,
            )
            .execute()
        )
        # Return the Google Meet join link, fall back to calendar event link
        meet_link = ""
        for entry in created.get("conferenceData", {}).get("entryPoints", []):
            if entry.get("entryPointType") == "video":
                meet_link = entry.get("uri", "")
                break
        link = meet_link or created.get("htmlLink", "")
        logger.info("calendar_event_created", candidate=candidate_name, link=link)
        return link
    except Exception as exc:
        logger.error("calendar_event_creation_failed", error=str(exc))
        return ""
