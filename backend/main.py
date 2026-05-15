from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import analyze, competitors, reports, websocket, webhooks
from backend.config import settings
from backend.models.database import init_db
from backend.services.background import resume_interrupted_workflows
from backend.services.checkpointer import init_checkpointer, shutdown_checkpointer
from backend.services.logger import configure_logging
from backend.services.scheduler import start_scheduler, stop_scheduler


configure_logging()

app = FastAPI(title="ASCENT Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)
app.include_router(analyze.router)
app.include_router(reports.router)
app.include_router(competitors.router)
app.include_router(websocket.router)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    init_checkpointer()
    await resume_interrupted_workflows()
    start_scheduler()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    stop_scheduler()
    shutdown_checkpointer()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
