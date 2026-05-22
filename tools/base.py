import time
import asyncio
import functools
from typing import Callable, TypeVar, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
from core.logging import get_logger
from core.observability import build_metric
from config.settings import get_settings

logger = get_logger("tools.base")
_settings = get_settings()

T = TypeVar("T")


def with_retry(
    max_attempts: int | None = None,
    wait_seconds: float | None = None,
    reraise_on: tuple[type[Exception], ...] = (Exception,),
):
    """Tenacity retry decorator pre-configured for tool calls."""
    attempts = max_attempts or _settings.tool_max_retries
    wait = wait_seconds or _settings.tool_retry_wait_seconds

    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=wait, min=wait, max=wait * 8),
        retry=retry_if_exception_type(reraise_on),
        before_sleep=before_sleep_log(logging.getLogger("tools.retry"), logging.WARNING),
        reraise=True,
    )


def tool_call(name: str, kind: str = "tool"):
    """
    Decorator: wraps a tool function with timing, structured logging,
    and metric emission. Works for both sync and async functions.
    """
    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                error = None
                result = None
                logger.info(f"{kind}_call", name=name, args=str(args)[:300], kwargs=str(kwargs)[:300])
                try:
                    result = await fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    error = str(exc)
                    logger.error(f"{kind}_error", name=name, error=error)
                    raise
                finally:
                    latency_ms = (time.perf_counter() - start) * 1000
                    tokens_in = result.get("tokens_in") if isinstance(result, dict) else getattr(result, "tokens_in", None)
                    tokens_out = result.get("tokens_out") if isinstance(result, dict) else getattr(result, "tokens_out", None)
                    build_metric(
                        name=name,
                        kind=kind,
                        input_data={"args": str(args)[:400], "kwargs": str(kwargs)[:400]},
                        output_data=str(result)[:400] if result else None,
                        latency_ms=latency_ms,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        error=error,
                    )
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                error = None
                result = None
                logger.info(f"{kind}_call", name=name, args=str(args)[:300], kwargs=str(kwargs)[:300])
                try:
                    result = fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    error = str(exc)
                    logger.error(f"{kind}_error", name=name, error=error)
                    raise
                finally:
                    latency_ms = (time.perf_counter() - start) * 1000
                    tokens_in = result.get("tokens_in") if isinstance(result, dict) else getattr(result, "tokens_in", None)
                    tokens_out = result.get("tokens_out") if isinstance(result, dict) else getattr(result, "tokens_out", None)
                    build_metric(
                        name=name,
                        kind=kind,
                        input_data={"args": str(args)[:400], "kwargs": str(kwargs)[:400]},
                        output_data=str(result)[:400] if result else None,
                        latency_ms=latency_ms,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        error=error,
                    )
            return sync_wrapper
    return decorator
