from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import AsyncSessionLocal
from backend.models.schemas import SignalInput
from backend.models.tables import WebhookEvent
from backend.api.deps import require_database
from backend.services.background import dispatch_pipeline, enqueue_pipeline_run

router = APIRouter()


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/webhooks/news", status_code=status.HTTP_202_ACCEPTED)
async def receive_news(
    payload: SignalInput,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_database),
) -> dict[str, object]:
    webhook = WebhookEvent(
        source=payload.source or "news",
        title=payload.title,
        url=payload.url,
        payload=payload.model_dump(exclude_none=True),
    )
    session.add(webhook)
    await session.commit()
    await session.refresh(webhook)

    background_tasks.add_task(dispatch_pipeline, webhook.id, payload.model_dump(exclude_none=True))
    return {"status": "accepted", "webhook_id": webhook.id}


@router.post("/webhooks/scheduled", status_code=status.HTTP_202_ACCEPTED)
async def receive_scheduled(
    payload: SignalInput,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_database),
) -> dict[str, object]:
    async def _run() -> None:
        await enqueue_pipeline_run(payload, source=payload.source or "scheduled")

    background_tasks.add_task(_run)
    return {"status": "accepted", "message": "Scheduled scan queued"}
