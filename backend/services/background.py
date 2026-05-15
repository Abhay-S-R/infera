"""
ASCENT Background Pipeline Dispatcher.

Called by webhook/analyze endpoints as a FastAPI BackgroundTask.
Runs the full LangGraph agent pipeline and saves results to the database.
"""
from sqlalchemy import select

from backend.models.database import AsyncSessionLocal
from backend.models.tables import Workflow, Report
from backend.models.schemas import SignalInput
from backend.agents.graph import run_pipeline
from backend.services.checkpointer import get_checkpointer
from backend.services.events import publish_event
from backend.services.logger import get_logger

logger = get_logger("dispatcher")


async def _complete_workflow(
    session,
    workflow: Workflow,
    result: dict,
    workflow_id: str,
    webhook_id: int,
) -> None:
    """Persist report and mark workflow completed."""
    report_output = result.get("report_output")
    if report_output:
        report = Report(
            workflow_id=workflow.id,
            title=report_output.title,
            status="published",
            markdown=report_output.full_report_markdown,
            confidence=str(report_output.confidence_score),
            sources=report_output.sources,
        )
        session.add(report)

    workflow.status = "completed"
    workflow.current_agent = "done"
    session.add(workflow)
    await session.commit()

    logger.info(
        "pipeline_completed",
        workflow_id=workflow_id,
        report_title=report_output.title if report_output else "No report",
    )

    await publish_event("workflow.completed", {
        "workflow_id": workflow_id,
        "webhook_id": webhook_id,
        "status": "completed",
        "message": f"Report generated: {report_output.title}" if report_output else "Pipeline completed",
    })


async def _fail_workflow(
    session,
    workflow: Workflow,
    workflow_id: str,
    webhook_id: int,
    error: Exception,
) -> None:
    logger.error("pipeline_failed", workflow_id=workflow_id, error=str(error))

    workflow.status = "failed"
    workflow.extra_data = {**(workflow.extra_data or {}), "error": str(error)[:500]}
    session.add(workflow)
    await session.commit()

    await publish_event("workflow.failed", {
        "workflow_id": workflow_id,
        "webhook_id": webhook_id,
        "status": "failed",
        "message": f"Pipeline failed: {str(error)[:200]}",
    })


async def _execute_pipeline(
    workflow_id: int,
    webhook_id: int,
    payload: dict[str, object],
    *,
    resume: bool = False,
) -> None:
    """Run or resume the LangGraph pipeline for an existing workflow row."""
    wf_id_str = str(workflow_id)
    checkpointer = get_checkpointer()

    async with AsyncSessionLocal() as session:
        workflow = await session.get(Workflow, workflow_id)
        if workflow is None:
            logger.error("workflow_not_found", workflow_id=workflow_id)
            return

        if not resume:
            await publish_event("workflow.started", {
                "workflow_id": wf_id_str,
                "webhook_id": webhook_id,
                "current_agent": workflow.current_agent or "sentinel",
                "message": "Pipeline started",
            })
            logger.info("pipeline_started", workflow_id=wf_id_str, webhook_id=webhook_id)
        else:
            await publish_event("workflow.resumed", {
                "workflow_id": wf_id_str,
                "webhook_id": webhook_id,
                "current_agent": workflow.current_agent,
                "message": "Resuming pipeline from last checkpoint",
            })
            logger.info("pipeline_resumed", workflow_id=wf_id_str, webhook_id=webhook_id)

        try:
            if resume:
                result = await run_pipeline(
                    workflow_id=wf_id_str,
                    checkpointer=checkpointer,
                    resume=True,
                )
            else:
                signal = SignalInput(**payload)
                result = await run_pipeline(
                    signal,
                    workflow_id=wf_id_str,
                    checkpointer=checkpointer,
                )

            await _complete_workflow(session, workflow, result, wf_id_str, webhook_id)

        except Exception as e:
            await _fail_workflow(session, workflow, wf_id_str, webhook_id, e)


async def dispatch_pipeline(webhook_id: int, payload: dict[str, object]) -> None:
    """
    Run the full ASCENT agent pipeline in the background.

    1. Create a Workflow record (status=running)
    2. Run the LangGraph pipeline (Sentinel→Scout→Strategist→Arbiter→Scribe)
    3. Save the report to the Report table
    4. Update the Workflow record (status=completed or failed)
    """
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
        workflow_id = workflow.id

    await _execute_pipeline(workflow_id, webhook_id, payload, resume=False)


async def resume_interrupted_workflows() -> None:
    """On startup, resume any workflows that were still running when the process died."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Workflow).where(Workflow.status == "running")
        )
        interrupted = result.scalars().all()

    if not interrupted:
        logger.info("no_interrupted_workflows")
        return

    logger.info("resuming_interrupted_workflows", count=len(interrupted))

    for workflow in interrupted:
        payload = workflow.extra_data if isinstance(workflow.extra_data, dict) else {}
        webhook_id = workflow.webhook_id or 0
        await _execute_pipeline(workflow.id, webhook_id, payload, resume=True)
