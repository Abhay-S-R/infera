"""
Phase 2a Dev 1 — Checkpointer, competitors API, scheduler, crash recovery.

Run from project root (Postgres required via docker compose):
    python tests/test_phase2a_dev1.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import traceback
import uuid
from unittest.mock import AsyncMock, patch

# Set DB URLs before backend imports (docker-compose maps host 5433 -> container 5432)
os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://infera:infera_pass@localhost:5433/infera_db",
)
os.environ["DATABASE_URL_SYNC"] = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://infera:infera_pass@localhost:5433/infera_db",
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, bool]] = []


def log(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed))
    print(f"  {PASS if passed else FAIL}  {name}")
    if detail:
        for line in detail.split("\n")[:6]:
            print(f"         {line}")
    print()


async def test_database_and_tables() -> bool:
    from backend.core.database import init_db, AsyncSessionLocal
    from backend.models.tables import Competitor, Workflow
    from sqlalchemy import select

    await init_db()
    async with AsyncSessionLocal() as session:
        comp = Competitor(name="_test_co", industry="tech", keywords=["ai"], active=True)
        session.add(comp)
        await session.commit()
        await session.refresh(comp)
        comp_id = comp.id

        row = await session.get(Competitor, comp_id)
        ok = row is not None and row.name == "_test_co"

        await session.delete(row)
        await session.commit()


    log("Database init + Competitor table", ok, f"Inserted competitor id={comp_id}")
    return ok


async def test_checkpointer_setup() -> bool:
    from backend.pipeline.checkpointer import init_checkpointer, get_checkpointer, shutdown_checkpointer

    saver = await init_checkpointer()
    same = await get_checkpointer()
    ok = saver is same and saver is not None

    await shutdown_checkpointer()
    log("PostgresSaver init + setup", ok, "Checkpointer tables ready")
    return ok


async def test_graph_compiles_with_checkpointer() -> bool:
    from backend.agents.graph import build_graph, pipeline_config
    from backend.pipeline.checkpointer import init_checkpointer, shutdown_checkpointer

    checkpointer = await init_checkpointer()
    graph = build_graph(checkpointer=checkpointer)
    config = pipeline_config("test-thread-123")
    ok = graph is not None and config["configurable"]["thread_id"] == "test-thread-123"

    await shutdown_checkpointer()
    log("build_graph(checkpointer=...) compiles", ok)
    return ok


async def test_competitors_api_crud() -> bool:
    from httpx import ASGITransport, AsyncClient
    from backend.main import app
    from backend.core.database import init_db
    from backend.pipeline.checkpointer import init_checkpointer, shutdown_checkpointer
    from backend.pipeline.scheduler import stop_scheduler

    await init_db()
    await init_checkpointer()
    unique = f"TestCo_{uuid.uuid4().hex[:8]}"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            create = await client.post(
                "/api/competitors",
                json={
                    "name": unique,
                    "industry": "AI",
                    "keywords": ["llm", "chips"],
                    "active": True,
                },
            )
            if create.status_code != 201:
                log("Competitors API CRUD", False, f"POST failed: {create.status_code} {create.text}")
                return False

            created = create.json()
            comp_id = created["id"]

            listing = await client.get("/api/competitors")
            names = [c["name"] for c in listing.json()]
            found = unique in names

            deleted = await client.delete(f"/api/competitors/{comp_id}")
            gone = deleted.status_code == 204

            listing2 = await client.get("/api/competitors")
            still_there = any(c["id"] == comp_id for c in listing2.json())

            ok = found and gone and not still_there
            log("Competitors API CRUD", ok, f"Created id={comp_id}, listed, deleted")
            return ok
    finally:
        stop_scheduler()
        await shutdown_checkpointer()


async def test_scheduler_registers_job() -> bool:
    from backend.pipeline.scheduler import start_scheduler, stop_scheduler, _scheduler
    from backend.core.config import settings

    stop_scheduler()
    sched = start_scheduler()
    ok = sched is not None and sched.running
    if ok:
        job = sched.get_job("competitive_scans")
        ok = job is not None
        if ok and hasattr(job.trigger, "interval"):
            ok = job.trigger.interval.total_seconds() == settings.SCHEDULER_INTERVAL_MINUTES * 60

    stop_scheduler()
    log("APScheduler competitive_scans job", ok, f"Interval={settings.SCHEDULER_INTERVAL_MINUTES}min")
    return ok


async def test_resume_interrupted_workflows() -> bool:
    from backend.core.database import AsyncSessionLocal, init_db
    from backend.models.tables import Workflow, WebhookEvent
    from backend.pipeline.executor import resume_interrupted_workflows
    from backend.pipeline.checkpointer import init_checkpointer, shutdown_checkpointer

    await init_db()
    await init_checkpointer()

    async with AsyncSessionLocal() as session:
        webhook = WebhookEvent(
            source="test",
            title="Resume test signal",
            payload={"title": "Resume test", "source": "test"},
        )
        session.add(webhook)
        await session.commit()
        await session.refresh(webhook)

        workflow = Workflow(
            webhook_id=webhook.id,
            status="running",
            current_agent="scout",
            extra_data={"title": "Resume test", "source": "test"},
        )
        session.add(workflow)
        await session.commit()
        await session.refresh(workflow)
        workflow_id = workflow.id

    mock_result = {
        "report_output": None,
        "current_agent": "done",
    }

    with patch("backend.pipeline.executor.run_pipeline", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result
        await resume_interrupted_workflows()

        ok = mock_run.called
        if ok:
            kwargs = mock_run.call_args.kwargs
            ok = kwargs.get("resume") is True and kwargs.get("workflow_id") == str(workflow_id)

    async with AsyncSessionLocal() as session:
        wf = await session.get(Workflow, workflow_id)
        if wf:
            await session.delete(wf)
        wh = await session.get(WebhookEvent, webhook.id)
        if wh:
            await session.delete(wh)
        await session.commit()

    await shutdown_checkpointer()
    log("resume_interrupted_workflows()", ok, f"Resumed workflow id={workflow_id}")
    return ok


async def test_checkpoint_tables_exist() -> bool:
    """PostgresSaver.setup() creates LangGraph checkpoint tables."""
    import psycopg
    from backend.core.config import settings
    from backend.pipeline.checkpointer import init_checkpointer, shutdown_checkpointer

    await init_checkpointer()
    tables: list[str] = []
    try:
        with psycopg.connect(settings.DATABASE_URL_SYNC) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                      AND (tablename LIKE 'checkpoint%' OR tablename LIKE '%checkpoints%')
                    ORDER BY tablename
                    """
                )
                tables = [row[0] for row in cur.fetchall()]
    finally:
        await shutdown_checkpointer()

    ok = len(tables) > 0
    log("LangGraph checkpoint tables in Postgres", ok, ", ".join(tables) or "none found")
    return ok


async def main() -> None:
    print()
    print("=" * 60)
    print("  INFERA Phase 2a Dev 1 — Verification")
    print("=" * 60)
    print()

    tests = [
        ("Database + Competitor table", test_database_and_tables),
        ("PostgresSaver setup", test_checkpointer_setup),
        ("Graph + checkpointer compile", test_graph_compiles_with_checkpointer),
        ("Competitors API CRUD", test_competitors_api_crud),
        ("APScheduler job", test_scheduler_registers_job),
        ("Resume interrupted workflows", test_resume_interrupted_workflows),
        ("LangGraph checkpoint tables", test_checkpoint_tables_exist),
    ]

    for name, fn in tests:
        try:
            await fn()
        except Exception:
            log(name, False, traceback.format_exc())

    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"  RESULTS: {passed}/{total} tests passed")
    print("=" * 60)

    if passed < total:
        print("\n  Failed:")
        for name, ok in results:
            if not ok:
                print(f"    - {name}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
