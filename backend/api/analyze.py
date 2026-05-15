from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import AsyncSessionLocal
from backend.models.schemas import SignalInput
from backend.models.tables import WebhookEvent
from backend.services.background import dispatch_pipeline

router = APIRouter(prefix="/api")


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/analyze", status_code=status.HTTP_202_ACCEPTED)
async def manual_analyze(
    payload: SignalInput,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    webhook = WebhookEvent(
        source=payload.source or "manual",
        title=payload.title,
        url=payload.url,
        payload=payload.model_dump(exclude_none=True),
    )
    session.add(webhook)
    await session.commit()
    await session.refresh(webhook)

    background_tasks.add_task(dispatch_pipeline, webhook.id, payload.model_dump(exclude_none=True))
    return {"status": "accepted", "webhook_id": webhook.id}
