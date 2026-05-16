from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import analyze, competitors, health, reports, webhooks
from backend.api import websocket
from backend.core.config import settings
from backend.core.database import (
    check_database_connection,
    init_db,
    is_database_available,
    set_database_available,
)
from backend.pipeline.executor import resume_interrupted_workflows
from backend.pipeline.checkpointer import init_checkpointer, shutdown_checkpointer  # async
from backend.core.logger import configure_logging, get_logger
from backend.pipeline.scheduler import start_scheduler, stop_scheduler
from backend.core.tracing import init_omium

configure_logging()
logger = get_logger("main")

app = FastAPI(title="ASCENT Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)
app.include_router(analyze.router)
app.include_router(reports.router)
app.include_router(competitors.router)
app.include_router(health.router)
app.include_router(websocket.router)

_DB_REQUIRED_PREFIXES = ("/api/", "/webhooks/")


@app.middleware("http")
async def database_availability_middleware(request: Request, call_next):
    """Return 503 for API/webhook routes when Postgres is down."""
    if request.url.path.startswith(_DB_REQUIRED_PREFIXES):
        if not await is_database_available():
            return JSONResponse(
                status_code=503,
                content={"detail": "Database unavailable"},
            )
    return await call_next(request)


@app.on_event("startup")
async def on_startup() -> None:
    init_omium()  # Initialize Omium tracing with API credentials
    await init_db()
    await init_checkpointer()
    await resume_interrupted_workflows()
    start_scheduler()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    stop_scheduler()
    await shutdown_checkpointer()


@app.get("/health")
async def health():
    """Liveness check — 503 when Postgres is unreachable."""
    if await is_database_available():
        return {"status": "ok", "database": "up"}
    return JSONResponse(
        status_code=503,
        content={"status": "unavailable", "database": "down"},
    )
