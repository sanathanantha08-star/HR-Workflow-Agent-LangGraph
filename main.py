import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from core.logging import setup_logging, get_logger
from core.exceptions import register_exception_handlers
from db.mongodb import connect as db_connect, disconnect as db_disconnect
from graph.workflow import build_graph
from api.router import api_router
from config.settings import get_settings

setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("startup", env=settings.env, port=settings.app_port)

    await db_connect()
    build_graph()

    logger.info("ready")
    yield

    await db_disconnect()
    logger.info("shutdown")


app = FastAPI(
    title="HR Workflow Automation",
    description=(
        "Multi-agent LangGraph system for end-to-end HR workflow: "
        "resume shortlisting → HITL approval → pre-screening calls → HITL approval."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Serve TTS audio files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

register_exception_handlers(app)
app.include_router(api_router)

# Serve frontend SPA
_frontend = Path(__file__).parent / "frontend"

@app.get("/", response_class=FileResponse)
async def serve_frontend():
    return FileResponse(_frontend / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=True)
