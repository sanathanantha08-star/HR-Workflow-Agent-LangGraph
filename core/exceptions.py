from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from core.logging import get_logger

logger = get_logger("exceptions")


class HRWorkflowError(Exception):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class ResumeParseError(HRWorkflowError):
    pass


class LLMError(HRWorkflowError):
    pass


class CallError(HRWorkflowError):
    pass


class DatabaseError(HRWorkflowError):
    pass


class SessionNotFoundError(HRWorkflowError):
    pass


class HITLError(HRWorkflowError):
    pass


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HRWorkflowError)
    async def hr_workflow_error_handler(request: Request, exc: HRWorkflowError):
        logger.error(
            "hr_workflow_error",
            error_type=type(exc).__name__,
            message=str(exc),
            details=exc.details,
            path=str(request.url),
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": type(exc).__name__,
                "message": str(exc),
                "details": exc.details,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.error("validation_error", message=str(exc), path=str(request.url))
        return JSONResponse(
            status_code=422,
            content={"error": "ValidationError", "message": str(exc)},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "unhandled_exception",
            error_type=type(exc).__name__,
            message=str(exc),
            path=str(request.url),
        )
        return JSONResponse(
            status_code=500,
            content={"error": "InternalServerError", "message": "An unexpected error occurred"},
        )
