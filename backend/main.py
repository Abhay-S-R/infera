from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import analyze, reports, websocket, webhooks
from backend.config import settings
from backend.models.database import init_db
from backend.services.logger import configure_logging


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
app.include_router(websocket.router)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
