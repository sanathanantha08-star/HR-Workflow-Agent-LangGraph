import time
import functools
import asyncio
from typing import Any, Callable, Optional
from core.logging import get_logger

logger = get_logger("observability")


def build_metric(
    name: str,
    kind: str,                  # "agent" | "tool"
    input_data: Any,
    output_data: Any,
    latency_ms: float,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    error: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    metric = {
        "name": name,
        "kind": kind,
        "latency_ms": round(latency_ms, 2),
        "input": input_data,
        "output": output_data,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "error": error,
        **(extra or {}),
    }
    logger.info(
        "metric",
        **{k: v for k, v in metric.items() if v is not None},
    )
    return metric


def observe_tool(name: str):
    """Decorator that measures latency and logs i/o for a tool function."""
    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                error = None
                result = None
                try:
                    result = await fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    error = str(exc)
                    raise
                finally:
                    latency_ms = (time.perf_counter() - start) * 1000
                    build_metric(
                        name=name,
                        kind="tool",
                        input_data={"args": str(args)[:500], "kwargs": str(kwargs)[:500]},
                        output_data=str(result)[:500] if result is not None else None,
                        latency_ms=latency_ms,
                        error=error,
                    )
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                error = None
                result = None
                try:
                    result = fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    error = str(exc)
                    raise
                finally:
                    latency_ms = (time.perf_counter() - start) * 1000
                    build_metric(
                        name=name,
                        kind="tool",
                        input_data={"args": str(args)[:500], "kwargs": str(kwargs)[:500]},
                        output_data=str(result)[:500] if result is not None else None,
                        latency_ms=latency_ms,
                        error=error,
                    )
            return sync_wrapper
    return decorator


def observe_agent(name: str):
    """Decorator that measures latency and logs i/o for an agent node."""
    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                error = None
                result = None
                logger.info("agent_start", agent=name)
                try:
                    result = await fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    error = str(exc)
                    raise
                finally:
                    latency_ms = (time.perf_counter() - start) * 1000
                    logger.info(
                        "agent_end",
                        agent=name,
                        latency_ms=round(latency_ms, 2),
                        error=error,
                    )
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                error = None
                result = None
                logger.info("agent_start", agent=name)
                try:
                    result = fn(*args, **kwargs)
                    return result
                except Exception as exc:
                    error = str(exc)
                    raise
                finally:
                    latency_ms = (time.perf_counter() - start) * 1000
                    logger.info(
                        "agent_end",
                        agent=name,
                        latency_ms=round(latency_ms, 2),
                        error=error,
                    )
            return sync_wrapper
    return decorator
