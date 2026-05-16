"""
INFERA Health & cost stats API — Dev 4 Phase 2b.

Dashboard polls GET /api/health/stats for workflow/report/token aggregates.
"""
from fastapi import APIRouter
from sqlalchemy import func, select

from backend.core.database import AsyncSessionLocal
from backend.models.schemas import HealthStatsResponse
from backend.models.tables import Report, Workflow
from backend.core.budget import format_cost_usd

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/stats", response_model=HealthStatsResponse)
async def get_health_stats() -> HealthStatsResponse:
    """Aggregate pipeline cost and activity metrics for the dashboard health panel."""
    async with AsyncSessionLocal() as session:
        active = await session.scalar(
            select(func.count()).select_from(Workflow).where(Workflow.status == "running")
        )
        total_reports = await session.scalar(select(func.count()).select_from(Report))
        total_tokens = await session.scalar(
            select(func.coalesce(func.sum(Workflow.tokens_used), 0))
        )
        total_cost = await session.scalar(
            select(func.coalesce(func.sum(Workflow.estimated_cost), 0.0))
        )
        last_row = await session.execute(
            select(Workflow).order_by(Workflow.id.desc()).limit(1)
        )
        last_wf = last_row.scalar_one_or_none()

    last_error = None
    if last_wf and isinstance(last_wf.extra_data, dict):
        last_error = last_wf.extra_data.get("error") or None
        if last_error == "":
            last_error = None

    return HealthStatsResponse(
        active_workflows=int(active or 0),
        total_reports=int(total_reports or 0),
        total_tokens=int(total_tokens or 0),
        estimated_cost=format_cost_usd(float(total_cost or 0.0)),
        last_workflow_id=last_wf.id if last_wf else None,
        last_workflow_status=last_wf.status if last_wf else None,
        last_workflow_tokens=last_wf.tokens_used if last_wf else None,
        last_workflow_error=last_error,
    )
