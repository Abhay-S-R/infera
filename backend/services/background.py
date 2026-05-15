from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import AsyncSessionLocal
from backend.models.tables import Workflow
from backend.services.events import publish_event


async def dispatch_pipeline(webhook_id: int, payload: dict[str, object]) -> None:
    async with AsyncSessionLocal() as session:
        workflow = Workflow(
            webhook_id=webhook_id,
            status="running",
            current_agent="sentinel",
            extra_data=payload,
        )
        session.add(workflow)
        await session.commit()
        await session.refresh(workflow)

        await publish_event("workflow.started", {
            "workflow_id": workflow.id,
            "webhook_id": webhook_id,
            "current_agent": workflow.current_agent,
            "message": "Pipeline started",
        })

        workflow.status = "completed"
        workflow.current_agent = "scribe"
        session.add(workflow)
        await session.commit()

        await publish_event("workflow.completed", {
            "workflow_id": workflow.id,
            "webhook_id": webhook_id,
            "status": workflow.status,
            "message": "Pipeline completed as a stub.",
        })
