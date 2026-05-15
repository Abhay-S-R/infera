"""
Phase 2b Dev 1 — Crash recovery, scheduled scans, graceful degradation.

Run from project root (Postgres required; Redis optional):
    python tests/test_phase2b_dev1.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import traceback
import uuid
from unittest.mock import AsyncMock, patch

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://ascent:ascent_pass@localhost:5432/ascent_db",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql://ascent:ascent_pass@localhost:5432/ascent_db",
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


async def test_crash_recovery_resumes_at_scout() -> bool:
    """
    Simulate kill mid-Scout: checkpoint after Sentinel, resume continues at Scout.
    """
    from backend.agents.graph import build_graph, pipeline_config
    from backend.models.schemas import (
        SignalInput,
        SentinelOutput,
        EventType,
        AgentStatus,
        ResearchOutput,
        AnalysisOutput,
        ValidationResult,
        ReportOutput,
    )
    from backend.services.budget import TokenBudget
    from backend.services.checkpointer import init_checkpointer, shutdown_checkpointer

    checkpointer = await init_checkpointer()
    thread_id = f"crash-test-{uuid.uuid4().hex[:8]}"
    config = pipeline_config(thread_id)

    sentinel_calls = 0

    async def mock_sentinel(state):
        nonlocal sentinel_calls
        sentinel_calls += 1
        return {
            "sentinel_output": SentinelOutput(
                relevance_score=0.9,
                should_investigate=True,
                event_type=EventType.GENERAL,
                entities=["TestCo"],
                summary="Test signal summary",
                reasoning="High relevance",
            ),
            "current_agent": "sentinel",
            "activity_log": [],
        }

    async def mock_scout(state):
        return {
            "research_output": ResearchOutput(
                queries_used=["q1"],
                key_findings=["finding"],
                sources_consulted=1,
                raw_content_summary="summary",
            ),
            "current_agent": "scout",
            "activity_log": [],
        }

    async def mock_strategist(state):
        return {
            "analysis_output": AnalysisOutput(
                executive_summary="exec",
                market_impact="impact",
                competitive_positioning="pos",
                strategic_recommendations=["monitor"],
                overall_confidence=0.8,
            ),
            "current_agent": "strategist",
            "activity_log": [],
        }

    async def mock_arbiter(state):
        return {
            "validation_result": ValidationResult(
                is_approved=True,
                overall_confidence=0.8,
            ),
            "current_agent": "arbiter",
            "activity_log": [],
        }

    async def mock_scribe(state):
        return {
            "report_output": ReportOutput(
                title="Test Report",
                executive_summary="exec",
                full_report_markdown="# Report",
                confidence_score=0.8,
            ),
            "current_agent": "scribe",
            "activity_log": [],
        }

    patches = [
        patch("backend.agents.graph.sentinel_node", mock_sentinel),
        patch("backend.agents.graph.scout_node", mock_scout),
        patch("backend.agents.graph.strategist_node", mock_strategist),
        patch("backend.agents.graph.arbiter_node", mock_arbiter),
        patch("backend.agents.graph.scribe_node", mock_scribe),
    ]

    try:
        for p in patches:
            p.start()

        graph = build_graph(checkpointer=checkpointer, interrupt_before=["scout"])
        signal = SignalInput(title="Crash recovery test", source="test")
        budget = TokenBudget()
        initial = {
            "signal": signal,
            "workflow_id": thread_id,
            "retry_count": 0,
            "max_retries": 3,
            "should_continue": True,
            "current_agent": "sentinel",
            "error": None,
            "activity_log": [],
            "token_budget": budget.to_dict(),
            "total_tokens_used": 0,
            "total_cost_usd": 0.0,
            "budget_exceeded": False,
        }

        await graph.ainvoke(initial, config=config)
        snapshot = await graph.aget_state(config)
        next_nodes = [str(n) for n in (snapshot.next or ())]
        has_sentinel = snapshot.values.get("sentinel_output") is not None
        paused_before_scout = any("scout" in n for n in next_nodes)

        sentinel_calls_before_resume = sentinel_calls
        await graph.ainvoke(None, config=config)
        sentinel_calls_after = sentinel_calls

        ok = (
            has_sentinel
            and paused_before_scout
            and sentinel_calls_before_resume == 1
            and sentinel_calls_after == 1
        )
        detail = (
            f"next={next_nodes}, sentinel_calls={sentinel_calls_after}, "
            f"has_sentinel_output={has_sentinel}"
        )
        log("Crash recovery resumes at Scout (not Sentinel)", ok, detail)
        return ok
    finally:
        for p in patches:
            p.stop()
        await shutdown_checkpointer()


async def test_redis_publish_fails_silently() -> bool:
    from backend.services.events import publish_event

    with patch("backend.services.events.create_redis") as mock_redis:
        client = AsyncMock()
        client.publish.side_effect = ConnectionError("Redis down")
        client.close = AsyncMock()
        mock_redis.return_value = client

        try:
            await publish_event("test.event", {"agent": "scout"})
            ok = True
        except Exception as exc:
            ok = False
            detail = str(exc)
        else:
            detail = "No exception raised when Redis unavailable"

    log("Redis down: publish_event fails silently", ok, detail)
    return ok


async def test_scheduled_scan_signal_builder() -> bool:
    from backend.models.tables import Competitor
    from backend.services.scheduler import signal_for_competitor

    comp = Competitor(
        id=1,
        name="OpenAI",
        industry="AI",
        keywords=["gpt", "chips"],
        active=True,
    )
    signal = signal_for_competitor(comp)
    ok = (
        signal.source == "scheduled"
        and signal.competitor_name == "OpenAI"
        and "gpt" in (signal.custom_question or "")
    )
    log("Scheduler builds SignalInput from competitor", ok, signal.custom_question or "")
    return ok


async def test_postgres_503_middleware() -> bool:
    from httpx import ASGITransport, AsyncClient
    from backend.main import app

    with patch("backend.main.is_database_available", AsyncMock(return_value=False)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/competitors")

    ok = resp.status_code == 503
    log("Postgres down: API returns 503", ok, f"status={resp.status_code} body={resp.text[:80]}")
    return ok


async def test_health_503_when_db_down() -> bool:
    from httpx import ASGITransport, AsyncClient
    from backend.main import app

    with patch("backend.main.is_database_available", AsyncMock(return_value=False)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")

    ok = resp.status_code == 503
    log("Postgres down: GET /health returns 503", ok, f"status={resp.status_code}")
    return ok


async def main() -> None:
    print()
    print("=" * 60)
    print("  ASCENT Phase 2b Dev 1 — Verification")
    print("=" * 60)
    print()

    tests = [
        ("Crash recovery resumes at Scout", test_crash_recovery_resumes_at_scout),
        ("Redis publish fails silently", test_redis_publish_fails_silently),
        ("Scheduler SignalInput from competitor", test_scheduled_scan_signal_builder),
        ("API 503 when Postgres down", test_postgres_503_middleware),
        ("/health 503 when Postgres down", test_health_503_when_db_down),
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
        for name, ok in results:
            if not ok:
                print(f"    - {name}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
