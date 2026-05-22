import time
from abc import ABC, abstractmethod
from typing import Any
from core.logging import get_logger
from core.observability import build_metric

logger = get_logger("agents.base")


class BaseAgent(ABC):
    """Base class for all HR workflow agents with built-in observability."""

    name: str = "base_agent"

    def run(self, *args, **kwargs) -> Any:
        start = time.perf_counter()
        error = None
        result = None
        logger.info("agent_run_start", agent=self.name)
        try:
            result = self._run(*args, **kwargs)
            return result
        except Exception as exc:
            error = str(exc)
            logger.error("agent_run_error", agent=self.name, error=error)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            tokens_in = result.get("tokens_in") if isinstance(result, dict) else None
            tokens_out = result.get("tokens_out") if isinstance(result, dict) else None
            build_metric(
                name=self.name,
                kind="agent",
                input_data={"args": str(args)[:400], "kwargs": str(kwargs)[:400]},
                output_data=str(result)[:400] if result else None,
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                error=error,
            )

    async def arun(self, *args, **kwargs) -> Any:
        start = time.perf_counter()
        error = None
        result = None
        logger.info("agent_arun_start", agent=self.name)
        try:
            result = await self._arun(*args, **kwargs)
            return result
        except Exception as exc:
            error = str(exc)
            logger.error("agent_arun_error", agent=self.name, error=error)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            tokens_in = result.get("tokens_in") if isinstance(result, dict) else None
            tokens_out = result.get("tokens_out") if isinstance(result, dict) else None
            build_metric(
                name=self.name,
                kind="agent",
                input_data={"args": str(args)[:400], "kwargs": str(kwargs)[:400]},
                output_data=str(result)[:400] if result else None,
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                error=error,
            )

    def _run(self, *args, **kwargs) -> Any:
        raise NotImplementedError

    async def _arun(self, *args, **kwargs) -> Any:
        raise NotImplementedError
