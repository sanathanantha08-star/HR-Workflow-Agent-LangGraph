from db import mongodb as db
from core.logging import get_logger
from core.exceptions import DatabaseError
from tools.base import tool_call, with_retry

logger = get_logger("tools.storage")


@tool_call("store_file_bytes")
@with_retry(reraise_on=(Exception,))
async def store_file_bytes(filename: str, content: bytes, metadata: dict | None = None) -> str:
    """Store file bytes in GridFS, return file_id string."""
    try:
        return await db.store_file(filename, content, metadata)
    except Exception as exc:
        raise DatabaseError(f"Failed to store file '{filename}': {exc}") from exc


@tool_call("load_file_bytes")
@with_retry(reraise_on=(Exception,))
async def load_file_bytes(file_id: str) -> bytes:
    """Load file bytes from GridFS by file_id."""
    try:
        return await db.read_file(file_id)
    except Exception as exc:
        raise DatabaseError(f"Failed to load file '{file_id}': {exc}") from exc


@tool_call("save_session_state")
@with_retry(reraise_on=(Exception,))
async def save_session_state(session_id: str, state_snapshot: dict) -> None:
    """Persist current workflow state snapshot to MongoDB."""
    try:
        await db.update_session(session_id, state_snapshot)
        logger.info("session_state_saved", session_id=session_id, step=state_snapshot.get("current_step"))
    except Exception as exc:
        raise DatabaseError(f"Failed to save session state: {exc}") from exc


@tool_call("save_shortlisted_candidates")
@with_retry(reraise_on=(Exception,))
async def save_shortlisted_candidates(session_id: str, candidates: list[dict]) -> None:
    """Persist shortlisted candidates to MongoDB."""
    try:
        await db.save_candidates(session_id, candidates)
    except Exception as exc:
        raise DatabaseError(f"Failed to save candidates: {exc}") from exc


@tool_call("create_call_record")
@with_retry(reraise_on=(Exception,))
async def create_call_record(
    session_id: str, candidate_id: str, call_sid: str, phone: str
) -> None:
    """Create a call tracking record in MongoDB."""
    try:
        await db.create_call_record(session_id, candidate_id, call_sid, phone)
    except Exception as exc:
        raise DatabaseError(f"Failed to create call record: {exc}") from exc


@tool_call("update_call_status")
@with_retry(reraise_on=(Exception,))
async def update_call_status(call_sid: str, update: dict) -> None:
    """Update call record fields."""
    try:
        await db.update_call_record(call_sid, update)
    except Exception as exc:
        raise DatabaseError(f"Failed to update call '{call_sid}': {exc}") from exc


@tool_call("save_metric_record")
@with_retry(reraise_on=(Exception,))
async def save_metric_record(session_id: str, metric: dict) -> None:
    """Persist an observability metric to MongoDB."""
    try:
        await db.save_metric(session_id, metric)
    except Exception as exc:
        logger.warning("metric_save_failed", session_id=session_id, error=str(exc))
