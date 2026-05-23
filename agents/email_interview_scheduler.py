"""
Email Interview Scheduler Agent.

For each pre-screened candidate with interview_slots, this agent:
  1. Parses each slot string into a datetime range.
  2. Checks the recruiter's Google Calendar for that window.
  3. Picks the first free slot.
  4. Creates a Google Calendar event.
  5. Sends confirmation emails to the candidate and recruiter.
"""
import asyncio
import datetime
import re
from functools import partial

from agents.base import BaseAgent
from tools.calendar_tools import check_slot_free, create_calendar_event
from tools.email_tools import send_interview_emails
from core.logging import get_logger

logger = get_logger("agents.email_interview_scheduler")

# IST offset (UTC+5:30)
_IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def _parse_time(raw: str) -> datetime.time:
    """
    Parse strings like "8 AM", "12 PM", "8:30 AM".
    Pads single-digit hours so strptime is happy on all platforms.
    """
    t = raw.strip()
    # Pad "8 AM" → "08 AM"
    t = re.sub(r"^(\d) ", r"0\1 ", t)
    for fmt in ("%I:%M %p", "%I %p"):
        try:
            return datetime.datetime.strptime(t, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse time string: '{raw}'")


def _parse_slot(
    slot_str: str,
) -> tuple[datetime.datetime, datetime.datetime] | None:
    """
    Parse "Available on Monday, May 25 from 8 AM to 12 PM" into (start_dt, end_dt).
    Returns None if parsing fails.
    """
    pattern = (
        r"(?:Available on\s+)?"     # optional prefix
        r"(?:\w+,\s+)?"             # optional weekday + comma
        r"(\w+ \d+)"                # month + day  e.g. "May 25"
        r"\s+from\s+"
        r"([\d:]+\s*[AP]M)"         # start time
        r"\s+to\s+"
        r"([\d:]+\s*[AP]M)"         # end time
    )
    m = re.search(pattern, slot_str, re.IGNORECASE)
    if not m:
        logger.warning("slot_parse_no_match", slot=slot_str)
        return None

    date_part, start_raw, end_raw = m.group(1), m.group(2), m.group(3)
    year = datetime.date.today().year
    try:
        base_date = datetime.datetime.strptime(f"{date_part} {year}", "%B %d %Y").date()
    except ValueError:
        logger.warning("slot_parse_bad_date", date_part=date_part)
        return None

    try:
        start_t = _parse_time(start_raw)
        end_t   = _parse_time(end_raw)
    except ValueError as exc:
        logger.warning("slot_parse_bad_time", error=str(exc))
        return None

    start_dt = datetime.datetime.combine(base_date, start_t, tzinfo=_IST)
    end_dt   = datetime.datetime.combine(base_date, end_t,   tzinfo=_IST)

    if end_dt <= start_dt:
        logger.warning("slot_parse_inverted_times", slot=slot_str)
        return None

    return start_dt, end_dt


class EmailInterviewSchedulerAgent(BaseAgent):
    """
    Schedules interviews for all pre-screened candidates.
    Checks Google Calendar free/busy, creates events, and sends emails.
    """

    name = "email_interview_scheduler"

    async def _arun(
        self,
        session_id: str,
        pre_screening_results: list[dict],
    ) -> dict:
        logger.info(
            "scheduler_start",
            session_id=session_id,
            candidate_count=len(pre_screening_results),
        )

        loop = asyncio.get_event_loop()
        scheduling_results: list[dict] = []

        for candidate in pre_screening_results:
            cid    = candidate.get("candidate_id", "")
            name   = candidate.get("name", "Candidate")
            email  = candidate.get("email", "")
            slots  = candidate.get("interview_slots") or []

            if not slots:
                logger.warning("no_slots_for_candidate", candidate_id=cid, name=name)
                scheduling_results.append(self._result(cid, name, email, "no_slots"))
                continue

            INTERVIEW_DURATION = datetime.timedelta(hours=1)

            scheduled = False
            for slot_str in slots:
                parsed = _parse_slot(slot_str)
                if not parsed:
                    continue

                window_start, window_end = parsed

                # Scan 1-hour blocks within the candidate's availability window
                block_start = window_start
                while block_start + INTERVIEW_DURATION <= window_end:
                    block_end = block_start + INTERVIEW_DURATION

                    is_free = await loop.run_in_executor(
                        None, partial(check_slot_free, block_start, block_end)
                    )
                    if not is_free:
                        logger.info("slot_busy", candidate_id=cid, block_start=block_start.isoformat())
                        block_start += INTERVIEW_DURATION
                        continue

                    # Found a free 1-hour block — create calendar event
                    booked_slot = (
                        f"{block_start.strftime('%A, %B %d')} "
                        f"{block_start.strftime('%I:%M %p').lstrip('0')}–"
                        f"{block_end.strftime('%I:%M %p').lstrip('0')} IST"
                    )
                    try:
                        cal_link = await loop.run_in_executor(
                            None,
                            partial(create_calendar_event, name, email, block_start, block_end),
                        )

                        await loop.run_in_executor(
                            None,
                            partial(send_interview_emails, name, email, block_start, block_end, cal_link),
                        )

                        scheduling_results.append(
                            self._result(
                                cid, name, email, "scheduled",
                                scheduled_slot=booked_slot,
                                scheduled_at=block_start.isoformat(),
                                calendar_link=cal_link,
                            )
                        )
                        logger.info(
                            "interview_scheduled",
                            candidate_id=cid,
                            name=name,
                            slot=booked_slot,
                            calendar_link=cal_link,
                            session_id=session_id,
                        )
                        scheduled = True
                        break

                    except Exception as exc:
                        logger.error(
                            "scheduling_error",
                            candidate_id=cid,
                            slot=booked_slot,
                            error=str(exc),
                        )
                        block_start += INTERVIEW_DURATION
                        continue

                if scheduled:
                    break

            if not scheduled:
                scheduling_results.append(self._result(cid, name, email, "no_free_slot"))
                logger.warning("no_free_slot_found", candidate_id=cid, name=name)

        scheduled_count = sum(
            1 for r in scheduling_results if r["status"] == "scheduled"
        )
        logger.info(
            "scheduler_complete",
            session_id=session_id,
            total=len(scheduling_results),
            scheduled=scheduled_count,
        )

        return {
            "email_scheduling_results": scheduling_results,
            "tokens_in": 0,
            "tokens_out": 0,
        }

    @staticmethod
    def _result(
        candidate_id: str,
        name: str,
        email: str,
        status: str,
        scheduled_slot: str = "",
        scheduled_at: str = "",
        calendar_link: str = "",
    ) -> dict:
        return {
            "candidate_id":  candidate_id,
            "name":          name,
            "email":         email,
            "status":        status,        # scheduled | no_slots | no_free_slot
            "scheduled_slot": scheduled_slot,
            "scheduled_at":  scheduled_at,
            "calendar_link": calendar_link,
        }


email_interview_scheduler_agent = EmailInterviewSchedulerAgent()
