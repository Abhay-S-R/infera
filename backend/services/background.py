"""
ASCENT Background Pipeline Dispatcher.

Called by webhook/analyze endpoints as a FastAPI BackgroundTask.
Runs the full LangGraph agent pipeline and saves results to the database.
"""
from backend.models.database import AsyncSessionLocal
from backend.models.tables import Workflow, Report
from backend.models.schemas import SignalInput
from backend.agents.graph import run_pipeline
from backend.services.events import publish_event
from backend.services.logger import get_logger

logger = get_logger("dispatcher")


async def dispatch_pipeline(webhook_id: int, payload: dict[str, object]) -> None:
    """
    Run the full ASCENT agent pipeline in the background.

    1. Create a Workflow record (status=running)
    2. Run the LangGraph pipeline (Sentinel→Scout→Strategist→Arbiter→Scribe)
    3. Save the report to the Report table
    4. Update the Workflow record (status=completed or failed)
    """
    async with AsyncSessionLocal() as session:
        # ─── Create workflow record ───
        workflow = Workflow(
            webhook_id=webhook_id,
            status="running",
            current_agent="sentinel",
            extra_data=payload,
        )
        session.add(workflow)
        await session.commit()
        await session.refresh(workflow)

        workflow_id = str(workflow.id)

        await publish_event("workflow.started", {
            "workflow_id": workflow_id,
            "webhook_id": webhook_id,
            "current_agent": "sentinel",
            "message": "Pipeline started",
        })

        logger.info("pipeline_started", workflow_id=workflow_id, webhook_id=webhook_id)

        try:
            # ─── Build SignalInput from webhook payload ───
            signal = SignalInput(**payload)

            # ─── Run the real agent pipeline ───
            result = await run_pipeline(signal, workflow_id=workflow_id)

            # ─── Save report to DB ───
            report_output = result.get("report_output")
            budget_stopped = result.get("budget_exceeded") or (
                result.get("error") and "budget exceeded" in (result.get("error") or "").lower()
            )
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

            # ─── Update workflow as completed ───
            workflow.status = "completed"
            workflow.current_agent = "done"
            workflow.tokens_used = result.get("total_tokens_used", 0) or 0
            workflow.estimated_cost = result.get("total_cost_usd", 0.0) or 0.0
            if result.get("budget_exceeded") or (
                result.get("error") and "budget exceeded" in (result.get("error") or "").lower()
            ):
                workflow.status = "budget_exceeded"
                workflow.extra_data = {
                    **(workflow.extra_data or {}),
                    "budget_error": result.get("error"),
                }
            session.add(workflow)
            await session.commit()

            logger.info(
                "pipeline_completed",
                workflow_id=workflow_id,
                report_title=report_output.title if report_output else "No report",
                tokens_used=workflow.tokens_used,
                estimated_cost=workflow.estimated_cost,
            )

            completion_status = "budget_exceeded" if budget_stopped else "completed"
            completion_message = (
                result.get("error", "Token budget exceeded")
                if budget_stopped
                else (f"Report generated: {report_output.title}" if report_output else "Pipeline completed")
            )

            await publish_event("workflow.completed", {
                "workflow_id": workflow_id,
                "webhook_id": webhook_id,
                "status": completion_status,
                "message": completion_message,
                "tokens_used": workflow.tokens_used,
                "estimated_cost": workflow.estimated_cost,
            })

        except Exception as e:
            # ─── Handle pipeline failure ───
            logger.error("pipeline_failed", workflow_id=workflow_id, error=str(e))

            workflow.status = "failed"
            workflow.extra_data = {**(workflow.extra_data or {}), "error": str(e)[:500]}
            session.add(workflow)
            await session.commit()

            await publish_event("workflow.failed", {
                "workflow_id": workflow_id,
                "webhook_id": webhook_id,
                "status": "failed",
                "message": f"Pipeline failed: {str(e)[:200]}",
            })
