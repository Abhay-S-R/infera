from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.api.deps import require_database
from backend.models.database import AsyncSessionLocal
from backend.models.schemas import ReportDetailResponse, ReportListItem
from backend.models.tables import Report, Workflow

router = APIRouter(prefix="/api", dependencies=[Depends(require_database)])


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


def _competitor_from_workflow(workflow: Workflow | None) -> str | None:
    if workflow and isinstance(workflow.extra_data, dict):
        return workflow.extra_data.get("competitor_name")
    return None


def _documents_from_report(report: Report) -> dict[str, str]:
    if isinstance(report.documents, dict) and report.documents:
        return {k: str(v) for k, v in report.documents.items()}
    # Legacy single-blob reports
    fallback = report.markdown or ""
    return {
        "exec": fallback,
        "tech": fallback,
        "sales": fallback,
        "risk": fallback,
    }


@router.get("/reports")
async def list_reports(session: AsyncSession = Depends(get_session)) -> list[ReportListItem]:
    result = await session.execute(select(Report).order_by(Report.created_at.desc()))
    reports = result.scalars().all()
    items: list[ReportListItem] = []

    for report in reports:
        workflow = None
        if report.workflow_id:
            workflow = await session.get(Workflow, report.workflow_id)
        confidence = float(report.confidence) if report.confidence is not None else 0.0
        items.append(
            ReportListItem(
                id=report.id,
                title=report.title,
                competitor=_competitor_from_workflow(workflow),
                confidence=confidence,
                created_at=report.created_at,
            )
        )
    return items


@router.get("/reports/{report_id}")
async def get_report(report_id: int, session: AsyncSession = Depends(get_session)) -> ReportDetailResponse:
    result = await session.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    workflow = None
    if report.workflow_id:
        workflow = await session.get(Workflow, report.workflow_id)

    documents = _documents_from_report(report)
    confidence = float(report.confidence) if report.confidence is not None else 0.0

    return ReportDetailResponse(
        id=report.id,
        title=report.title,
        competitor=_competitor_from_workflow(workflow),
        confidence=confidence,
        created_at=report.created_at,
        executive_summary=documents.get("exec", "")[:500],
        full_report_markdown=report.markdown or documents.get("exec", ""),
        documents=documents,
        sources=report.sources or [],
    )
