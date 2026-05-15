"""
APScheduler — periodic competitive scans for tracked competitors.

Reads active competitors from the database and enqueues pipeline runs
via enqueue_pipeline_run (same path as POST /webhooks/scheduled).
"""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from backend.config import settings
from backend.models.database import AsyncSessionLocal
from backend.models.schemas import SignalInput
from backend.models.tables import Competitor
from backend.services.background import enqueue_pipeline_run
from backend.services.logger import get_logger

logger = get_logger("scheduler")

_scheduler: AsyncIOScheduler | None = None


def signal_for_competitor(competitor: Competitor) -> SignalInput:
    """Build a SignalInput for a scheduled competitive scan."""
    keywords = competitor.keywords or []
    keyword_text = ", ".join(keywords) if keywords else "general market activity"
    industry = competitor.industry or "their industry"

    return SignalInput(
        title=f"Scheduled scan: {competitor.name}",
        source="scheduled",
        competitor_name=competitor.name,
        custom_question=(
            f"What are the latest competitive developments for {competitor.name} "
            f"in {industry}? Focus on: {keyword_text}."
        ),
    )


async def run_scheduled_scans() -> None:
    """Generate a signal for each active competitor and start a pipeline."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Competitor).where(Competitor.active.is_(True))
        )
        competitors = result.scalars().all()

    if not competitors:
        logger.info("scheduled_scan_skipped", reason="no_active_competitors")
        return

    for competitor in competitors:
        signal = signal_for_competitor(competitor)
        result = await enqueue_pipeline_run(signal, source="scheduled")
        logger.info(
            "scheduled_scan_enqueued",
            competitor=competitor.name,
            webhook_id=result["webhook_id"],
        )


def start_scheduler() -> AsyncIOScheduler | None:
    """Start the periodic scan scheduler if enabled."""
    global _scheduler
    if not settings.SCHEDULER_ENABLED:
        logger.info("scheduler_disabled")
        return None

    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_scheduled_scans,
        IntervalTrigger(minutes=settings.SCHEDULER_INTERVAL_MINUTES),
        id="competitive_scans",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        "scheduler_started",
        interval_minutes=settings.SCHEDULER_INTERVAL_MINUTES,
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
    _scheduler = None
