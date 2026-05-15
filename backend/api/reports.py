from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.database import AsyncSessionLocal
from backend.models.schemas import ReportOutput
from backend.models.tables import Report

router = APIRouter(prefix="/api")


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@router.get("/reports")
async def list_reports(session: AsyncSession = Depends(get_session)) -> list[ReportOutput]:
    result = await session.execute(select(Report).order_by(Report.created_at.desc()))
    reports = result.scalars().all()
    return [
        ReportOutput(
            title=report.title,
            executive_summary=report.markdown or "",
            full_report_markdown=report.markdown or "",
            confidence_score=float(report.confidence) if report.confidence is not None else 0.0,
            sources=report.sources or [],
        )
        for report in reports
    ]


@router.get("/reports/{report_id}")
async def get_report(report_id: int, session: AsyncSession = Depends(get_session)) -> ReportOutput:
    result = await session.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportOutput(
        title=report.title,
        executive_summary=report.markdown or "",
        full_report_markdown=report.markdown or "",
        confidence_score=float(report.confidence) if report.confidence is not None else 0.0,
        sources=report.sources or [],
    )
