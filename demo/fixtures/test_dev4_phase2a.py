"""
Dev 4 Phase 2a — Token budget & context manager verification.

Run from project root:
    python demo/fixtures/test_dev4_phase2a.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.core.budget import TokenBudget, check_budget_or_stop, get_budget
from backend.pipeline.context import research_prompt_block
from backend.models.schemas import ResearchOutput
from backend.agents.state import PipelineState
from backend.models.schemas import SignalInput


def test_budget_tracker():
    budget = TokenBudget(max_tokens=10_000, max_cost_usd=2.0)
    assert budget.check_remaining() == 10_000
    budget.track("sentinel", 3000)
    budget.track("scout", 4000)
    assert budget.tokens_used == 7000
    assert budget.tier() == 2
    assert not budget.is_exceeded()
    budget.track("strategist", 5000)
    assert budget.is_exceeded()
    assert budget.check_remaining() == 0
    print("  PASS  TokenBudget track / tier / exceeded")


def test_budget_stop_response():
    state: PipelineState = {
        "workflow_id": "wf-test",
        "token_budget": {
            "max_tokens": 100,
            "max_cost_usd": 2.0,
            "tokens_used": 150,
            "cost_usd": 0.01,
            "by_agent": {"sentinel": 150},
        },
        "total_tokens_used": 150,
        "total_cost_usd": 0.01,
    }
    stopped = check_budget_or_stop(state, "scout", "wf-test")
    assert stopped is not None
    assert "budget exceeded" in stopped["error"].lower()
    assert stopped.get("should_continue") is False
    print("  PASS  check_budget_or_stop graceful message")


def test_context_tiers():
    budget = TokenBudget(max_tokens=100_000)
    budget.track("sentinel", 10_000)
    assert budget.tier() == 1

    budget.track("scout", 45_000)
    assert budget.tier() == 2

    research = ResearchOutput(
        queries_used=["q1"],
        key_findings=["Finding A", "Finding B"],
        sources_consulted=2,
        raw_content_summary="A" * 5000,
    )
    block_t1 = research_prompt_block(research, tier=1)
    block_t2 = research_prompt_block(research, tier=2)
    assert len(block_t1) > len(block_t2) or "Key Findings" in block_t2
    print("  PASS  Context tier prompt blocks")


async def test_low_budget_pipeline_stop():
    """Sentinel stops when budget is already exhausted (no full pipeline needed)."""
    from backend.agents.nodes.sentinel import sentinel_node
    from backend.core.budget import TokenBudget

    signal = SignalInput(
        title="Budget test signal",
        source="test",
        content="Minimal content for budget test.",
    )

    budget = TokenBudget(max_tokens=1)
    budget.track("preflight", 1)

    state: PipelineState = {
        "signal": signal,
        "workflow_id": "budget-test-wf",
        "token_budget": budget.to_dict(),
        "total_tokens_used": 1,
        "total_cost_usd": 0.0,
        "retry_count": 0,
        "max_retries": 3,
        "should_continue": True,
        "activity_log": [],
    }
    out = await sentinel_node(state)
    assert out.get("budget_exceeded") or "budget exceeded" in (out.get("error") or "").lower()
    print("  PASS  Sentinel stops when budget already exceeded")


async def main():
    print("========================================")
    print("DEV 4 PHASE 2a: BUDGET & CONTEXT TESTS")
    print("========================================\n")

    test_budget_tracker()
    test_budget_stop_response()
    test_context_tiers()
    await test_low_budget_pipeline_stop()

    print("\nAll Phase 2a Dev 4 checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
