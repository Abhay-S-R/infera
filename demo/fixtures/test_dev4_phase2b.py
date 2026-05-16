"""
Dev 4 Phase 2b — Cost stats API, context compression, token persistence.

Run from project root (Postgres via docker compose on port 5433):
    python demo/fixtures/test_dev4_phase2b.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://ascent:ascent_pass@localhost:5433/ascent_db",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql://ascent:ascent_pass@localhost:5433/ascent_db",
)


def test_format_cost():
    from backend.core.budget import format_cost_usd

    assert format_cost_usd(0.0) == "$0.00"
    assert format_cost_usd(12.345) == "$12.35"
    print("  PASS  format_cost_usd")


def test_estimate_state_tokens():
    from backend.pipeline.context import STATE_TOKEN_THRESHOLD, estimate_state_tokens
    from backend.models.schemas import ResearchOutput, SignalInput
    from backend.agents.state import PipelineState

    small: PipelineState = {
        "signal": SignalInput(title="Test", source="news", content="Short"),
        "research_output": ResearchOutput(
            queries_used=["q1"],
            key_findings=["a"],
            sources_consulted=1,
            raw_content_summary="Brief",
        ),
    }
    assert estimate_state_tokens(small) < STATE_TOKEN_THRESHOLD

    huge_summary = "x" * (STATE_TOKEN_THRESHOLD * 4 + 10_000)
    large: PipelineState = {
        **small,
        "research_output": ResearchOutput(
            queries_used=["q"] * 20,
            key_findings=["f"] * 50,
            sources_consulted=10,
            raw_content_summary=huge_summary,
        ),
    }
    assert estimate_state_tokens(large) > STATE_TOKEN_THRESHOLD
    print("  PASS  estimate_state_tokens threshold")


async def test_health_stats_api():
    from httpx import ASGITransport, AsyncClient
    from backend.main import app
    from backend.core.database import init_db, AsyncSessionLocal
    from backend.models.tables import Workflow, Report

    await init_db()

    async with AsyncSessionLocal() as session:
        wf = Workflow(
            webhook_id=None,
            status="completed",
            tokens_used=12_500,
            estimated_cost=0.05,
        )
        session.add(wf)
        session.add(
            Report(
                workflow_id=None,
                title="_phase2b_test_report",
                status="published",
                markdown="# test",
                confidence="0.9",
            )
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health/stats")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "active_workflows" in data
    assert "total_reports" in data
    assert data["total_tokens"] >= 12_500
    assert data["estimated_cost"].startswith("$")
    print(f"  PASS  GET /api/health/stats -> {data}")


async def test_compress_research_mocked():
    from unittest.mock import AsyncMock, patch

    from backend.core.budget import TokenBudget
    from backend.pipeline.context import SUMMARY_MAX_CHARS, compress_research_output
    from backend.models.schemas import ResearchOutput

    research = ResearchOutput(
        queries_used=["q1"],
        key_findings=["Finding A"],
        sources_consulted=1,
        raw_content_summary="A" * 5000,
    )
    budget = TokenBudget()

    with patch("backend.pipeline.context.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = ("Compressed summary text.", None)
        out = await compress_research_output(research, budget)

    assert len(out.raw_content_summary) <= SUMMARY_MAX_CHARS + 100
    mock_gen.assert_called_once()
    print("  PASS  compress_research_output (mocked LLM)")


async def main():
    print("========================================")
    print("DEV 4 PHASE 2b: COST & CONTEXT TESTS")
    print("========================================\n")

    test_format_cost()
    test_estimate_state_tokens()
    await test_compress_research_mocked()
    await test_health_stats_api()

    print("\nAll Phase 2b Dev 4 checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
