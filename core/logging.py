import json
import logging
import sys
import threading
from pathlib import Path

import structlog
from config.settings import get_settings

# ── Per-session file handles ────────────────────────────────────────────────
_file_handles: dict[str, object] = {}
_handle_lock = threading.Lock()


def bind_session_log(session_id: str) -> None:
    """
    Open a per-session JSONL log file and bind session_id to the current
    async context so every subsequent structlog call in this task is tagged
    and written to logs/<session_id>.jsonl.
    """
    structlog.contextvars.bind_contextvars(session_id=session_id)
    path = Path("logs") / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with _handle_lock:
        if session_id not in _file_handles:
            _file_handles[session_id] = open(path, "a", buffering=1)  # noqa: SIM115  # line-buffered


def _file_sink_processor(logger_instance, method: str, event_dict: dict) -> dict:
    """
    Structlog processor: runs before JSONRenderer.
    Writes a JSON line to the per-session file when session_id is in context.
    """
    sid = event_dict.get("session_id")
    if sid:
        fh = _file_handles.get(sid)
        if fh:
            try:
                fh.write(json.dumps(event_dict, default=str) + "\n")  # type: ignore[arg-type]
            except Exception:
                pass
    return event_dict


def setup_logging() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _file_sink_processor,          # ← write to file before rendering
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
