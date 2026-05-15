"""
ASCENT Background Pipeline Dispatcher.

Called by webhook/analyze endpoints as a FastAPI BackgroundTask.
Runs the full LangGraph agent pipeline and saves results to the database.
"""
from sqlalchemy import select

from backend.models.database import AsyncSessionLocal
from backend.models.tables import Workflow, Report
from backend.models.schemas import SignalInput
from backend.agents.graph import get_checkpoint_next_agent, run_pipeline
from backend.services.checkpointer import get_checkpointer
from backend.services.events import publish_event
from backend.services.budget import usage_from_pipeline_result
from backend.services.delivery import deliver_report
from backend.services.pdf_generator import write_report_pdf
from backend.services.profile_writer import update_competitor_profile_from_run
from backend.services.logger import get_logger

logger = get_logger("dispatcher")


def _format_pipeline_error(error: Exception) -> str:
    """Human-readable error for DB/logs (some exceptions have an empty str())."""
    msg = str(error).strip()
    if msg:
        return msg[:500]
    return f"{type(error).__name__}: {error!r}"[:500]


def _budget_stopped(result: dict) -> bool:
    if result.get("budget_exceeded"):
        return True
    err = result.get("error") or ""
    return "budget exceeded" in err.lower()


async def _complete_workflow(
    session,
    workflow: Workflow,
    result: dict,
    workflow_id: str,
    webhook_id: int,
) -> None:
    """Persist report, token usage, and mark workflow completed."""
    report_output = result.get("report_output")
    budget_stopped = _budget_stopped(result)

    delivery_result: dict[str, object] | None = None
    pdf_path: str | None = None
    competitor_name: str | None = None
    if isinstance(workflow.extra_data, dict):
        competitor_name = workflow.extra_data.get("competitor_name")

    # Profile write-back (Phase 4) — even if report missing, update memory when analysis exists
    analysis = result.get("analysis_output")
    signal_data = workflow.extra_data if isinstance(workflow.extra_data, dict) else {}
    try:
        from backend.models.schemas import SignalInput, SentinelOutput

        signal_obj = SignalInput(**signal_data) if signal_data.get("title") else None
        sentinel_obj = result.get("sentinel_output")
        if sentinel_obj and not competitor_name:
            competitor_name = (
                signal_obj.competitor_name if signal_obj else None
            ) or (sentinel_obj.resolved_competitor if hasattr(sentinel_obj, "resolved_competitor") else None)
            if not competitor_name and sentinel_obj.entities:
                competitor_name = sentinel_obj.entities[0]
        await update_competitor_profile_from_run(
            signal=signal_obj,
            sentinel=sentinel_obj if isinstance(sentinel_obj, SentinelOutput) else None,
            analysis=analysis,
            research_list=result.get("research_output"),
        )
    except Exception as exc:
        logger.warning("profile_writeback_skipped", workflow_id=workflow_id, error=str(exc)[:200])

    if report_output:
        combined_markdown = (
            f"# Executive Brief\n{report_output.exec_brief}\n\n"
            f"# Technical Breakdown\n{report_output.tech_brief}\n\n"
            f"# Sales Battle Card\n{report_output.sales_brief}\n\n"
            f"# Risk Register\n{report_output.risk_brief}"
        )
        report = Report(
            workflow_id=workflow.id,
            title=report_output.title,
            status="published",
            markdown=combined_markdown,
            documents={
                "exec": report_output.exec_brief,
                "tech": report_output.tech_brief,
                "sales": report_output.sales_brief,
                "risk": report_output.risk_brief,
            },
            confidence=str(report_output.confidence_score),
            sources=report_output.sources,
        )
        session.add(report)

    err_text = (result.get("error") or "").lower()
    if "unverified" in err_text and not report_output:
        workflow.status = "rejected"
    elif budget_stopped:
        workflow.status = "budget_exceeded"
    else:
        workflow.status = "completed"
    workflow.current_agent = "done"
    tokens, cost = usage_from_pipeline_result(result)
    workflow.tokens_used = tokens
    workflow.estimated_cost = cost
    extra = dict(workflow.extra_data or {})
    if budget_stopped:
        extra["budget_error"] = result.get("error")
    verification = result.get("verification_output")
    if verification is not None:
        extra["verification"] = verification.model_dump(mode="json")
    if competitor_name:
        extra["competitor_name"] = competitor_name
    workflow.extra_data = extra
    session.add(workflow)
    await session.commit()

    if report_output:
        try:
            pdf_path = write_report_pdf(report_output, workflow_id)
        except Exception as exc:
            logger.warning("pdf_exception", workflow_id=workflow_id, error=str(exc)[:200])

        try:
            delivery_result = await deliver_report(
                report_output,
                workflow_id=workflow_id,
                competitor=competitor_name,
            )
        except Exception as exc:
            logger.warning(
                "delivery_exception",
                workflow_id=workflow_id,
                error=str(exc)[:200],
            )

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

    completion_payload: dict[str, object] = {
        "workflow_id": workflow_id,
        "webhook_id": webhook_id,
        "status": completion_status,
        "message": completion_message,
        "tokens_used": workflow.tokens_used,
        "estimated_cost": workflow.estimated_cost,
    }
    if delivery_result:
        completion_payload["delivery"] = delivery_result
    if pdf_path:
        completion_payload["pdf_path"] = pdf_path
    await publish_event("workflow.completed", completion_payload)


async def _fail_workflow(
    session,
    workflow: Workflow,
    workflow_id: str,
    webhook_id: int,
    error: Exception,
    result: dict | None = None,
) -> None:
    err_msg = _format_pipeline_error(error)
    logger.error("pipeline_failed", workflow_id=workflow_id, error=err_msg, error_type=type(error).__name__)

    workflow.status = "failed"
    workflow.extra_data = {**(workflow.extra_data or {}), "error": err_msg}
    if result:
        workflow.tokens_used = result.get("total_tokens_used", 0) or workflow.tokens_used or 0
        workflow.estimated_cost = result.get("total_cost_usd", 0.0) or workflow.estimated_cost or 0.0
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
    checkpointer = await get_checkpointer()

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
            next_agent = await get_checkpoint_next_agent(wf_id_str, checkpointer)
            if next_agent:
                workflow.current_agent = next_agent
                session.add(workflow)
                await session.commit()

            await publish_event("workflow.resumed", {
                "workflow_id": wf_id_str,
                "webhook_id": webhook_id,
                "current_agent": workflow.current_agent,
                "message": f"Resuming pipeline from {workflow.current_agent}",
            })
            logger.info(
                "pipeline_resumed",
                workflow_id=wf_id_str,
                webhook_id=webhook_id,
                resume_from=workflow.current_agent,
            )

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
            partial: dict = {}
            try:
                partial = {
                    "total_tokens_used": workflow.tokens_used or 0,
                    "total_cost_usd": workflow.estimated_cost or 0.0,
                }
            except Exception:
                pass
            await _fail_workflow(session, workflow, wf_id_str, webhook_id, e, result=partial)


async def enqueue_pipeline_run(signal: SignalInput, *, source: str = "scheduled") -> dict[str, int]:
    """
    Create webhook + workflow records and start the pipeline.

    Used by APScheduler and POST /webhooks/scheduled.
    """
    payload = signal.model_dump(exclude_none=True)
    async with AsyncSessionLocal() as session:
        from backend.models.tables import WebhookEvent

        webhook = WebhookEvent(
            source=source,
            title=signal.title,
            url=signal.url,
            payload=payload,
        )
        session.add(webhook)
        await session.commit()
        await session.refresh(webhook)
        webhook_id = webhook.id

    await dispatch_pipeline(webhook_id, payload)
    return {"webhook_id": webhook_id}


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
