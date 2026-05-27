"""
Email sending via Gmail API (OAuth2) for interview scheduling confirmations.
Sends from sanath.anantha08@gmail.com to both the candidate and recruiter.

No App Password required — uses the same google_token.json as the calendar tool.
The token must be authorized by sanath.anantha08@gmail.com with the gmail.send scope.
"""
import base64
import datetime
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import get_settings
from core.logging import get_logger

logger = get_logger("tools.email")

AGENT_EMAIL     = "sanath.anantha08@gmail.com"
RECRUITER_EMAIL = "sanath.anantha07@gmail.com"


def _get_gmail_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    settings = get_settings()
    token_path = settings.google_token_path

    if not token_path or not os.path.exists(token_path):
        raise RuntimeError(
            f"Google token file not found at '{token_path}'. "
            "Run: python setup_google_auth.py"
        )

    with open(token_path) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_data.update({
            "token":  creds.token,
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
        })
        with open(token_path, "w") as f:
            json.dump(token_data, f)

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _fmt_dt(dt: datetime.datetime) -> tuple[str, str]:
    date_str = dt.strftime("%A, %B %d, %Y").replace(" 0", " ")
    time_str = dt.strftime("%I:%M %p").lstrip("0") or "12:00 AM"
    return date_str, time_str


def _make_raw(to: str, subject: str, body: str) -> dict:
    msg = MIMEMultipart()
    msg["From"]    = AGENT_EMAIL
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def send_interview_emails(
    candidate_name: str,
    candidate_email: str,
    start_dt: datetime.datetime,
    end_dt: datetime.datetime,
    calendar_link: str = "",
) -> bool:
    """
    Send interview confirmation to the candidate and a notification to the recruiter
    using the Gmail API. Returns True if both emails were sent successfully.
    """
    settings = get_settings()
    if not settings.google_token_path:
        logger.warning("google_token_not_configured_skipping_email")
        return False

    date_str, start_str = _fmt_dt(start_dt)
    _, end_str           = _fmt_dt(end_dt)
    meet_line = f"  Link     : {calendar_link}" if calendar_link else "  Link     : You will receive the meeting link shortly."

    messages = [
        (
            candidate_email,
            "Round 1 Interview Scheduled",
            f"""\
Dear {candidate_name},

We are pleased to inform you that your Round 1 interview has been scheduled. \
Please find the details below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Interview Details
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Date     : {date_str}
  Time     : {start_str} – {end_str} IST
  Duration : 1 Hour
  Mode     : Online (Google Meet)
{meet_line}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please join 5–10 minutes before the scheduled time and ensure your audio \
and video are working beforehand.

This is an automated email. Please do not reply to this message.

Regards,
Talent Acquisition Team""",
        ),
        (
            RECRUITER_EMAIL,
            f"Round 1 Interview Confirmed — {candidate_name} | {date_str}",
            f"""\
Hello,

A Round 1 interview has been confirmed with the following candidate. \
Please find the details below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Interview Details
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Candidate : {candidate_name}
  Email     : {candidate_email}
  Date      : {date_str}
  Time      : {start_str} – {end_str} IST
  Duration  : 1 Hour
  Mode      : Online (Google Meet)
{meet_line}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This notification was generated automatically by the HR Automation System.

Regards,
Talent Acquisition Team""",
        ),
    ]

    try:
        service = _get_gmail_service()
    except Exception as exc:
        logger.error("gmail_service_init_failed", error=str(exc))
        return False

    success = True
    for to_email, subject, body in messages:
        try:
            raw_msg = _make_raw(to_email, subject, body)
            service.users().messages().send(userId="me", body=raw_msg).execute()
            logger.info("email_sent", to=to_email, subject=subject)
        except Exception as exc:
            logger.error("email_send_failed", to=to_email, error=str(exc))
            success = False

    return success


def send_onboarding_email(candidate_name: str, candidate_email: str) -> bool:
    """Send a congratulations / onboarding email to a selected candidate."""
    settings = get_settings()
    if not settings.google_token_path:
        logger.warning("google_token_not_configured_skipping_onboarding_email")
        return False

    subject = "🎉 You're In! Welcome to the Team!"
    body = f"""\
Hey {candidate_name}! 🎊

We've got some AMAZING news for you — you've been selected! 🥳

Out of everyone who applied, you stood out and absolutely crushed it through the process. We're so excited to have you joining us!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🚀 What Happens Next
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📄  Your official offer letter is on its way (within 2 business days)
  📁  Start gathering your docs — ID proof, degree certificates, etc.
  📞  Our HR team will reach out soon to lock in your joining date

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Once again, a huge congratulations! 🙌 This is just the beginning of something great, and we can't wait to have you on board.

See you soon! 👋

Cheers,
The Talent Team ✨

───────────────────────────────────────
This is an automated message — please don't reply directly to this email."""

    try:
        service = _get_gmail_service()
        raw_msg = _make_raw(candidate_email, subject, body)
        service.users().messages().send(userId="me", body=raw_msg).execute()
        logger.info("onboarding_email_sent", to=candidate_email, candidate=candidate_name)
        return True
    except Exception as exc:
        logger.error("onboarding_email_failed", to=candidate_email, error=str(exc))
        return False
