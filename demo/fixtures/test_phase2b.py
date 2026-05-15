import asyncio
import os
import sys

# Ensure backend is in path
sys.path.append(os.getcwd())

from backend.models.schemas import SignalInput
from backend.agents.graph import run_pipeline
from backend.services.logger import configure_logging
from backend.services.budget import TokenBudget

async def test_normal_budget_tracking():
    print("\n--- TEST 1: Normal Budget Tracking ---")
    signal = SignalInput(
        title="Test Budget Tracking",
        source="news",
        content="This is a simple test to verify token tracking is working across all agents."
    )
    
    # We pass a fresh state with a standard budget
    result = await run_pipeline(signal, workflow_id="test-budget-001")
    
    budget = result.get("token_budget", {})
    tokens = result.get("total_tokens_used", 0)
    cost = result.get("total_cost_usd", 0.0)
    
    print(f"Tokens Used: {tokens}")
    print(f"Cost Estimate: ${cost:.4f}")
    print(f"Agent Breakdown: {budget.get('by_agent')}")
    
    if tokens > 0 and "sentinel" in budget.get("by_agent", {}):
        print("SUCCESS: Budget tracking functional.")
    else:
        print("FAILURE: No tokens tracked.")

async def test_budget_exhaustion():
    print("\n--- TEST 2: Budget Exhaustion ---")
    signal = SignalInput(
        title="CRITICAL: Microsoft acquires Anthropic for $100B",
        source="news",
        content="This is a massive industry-shifting event that must be investigated."
    )
    
    # Force a tiny budget (100 tokens). 
    # Sentinel will use ~700, so it will finish, but Scout should be BLOCKED.
    tiny_budget = TokenBudget(max_tokens=100).to_dict()
    
    result = await run_pipeline(
        signal, 
        workflow_id="test-exhaust-001",
        initial_state={"token_budget": tiny_budget}
    )
    
    if result.get("budget_exceeded") is True:
        print(f"SUCCESS: Pipeline stopped gracefully. Agent: {result.get('current_agent')}")
    else:
        print(f"FAILURE: Pipeline did not stop. Status: {result.get('current_agent')}, Tokens: {result.get('total_tokens_used')}")

async def test_context_compression_trigger():
    print("\n--- TEST 3: Context Compression (50k limit) ---")
    from backend.agents.strategist import strategist_node
    from backend.models.schemas import SentinelOutput, ResearchOutput
    
    # Phase 2b threshold is 50,000 tokens.
    massive_content = "Critical evidence data " * 20000 # ~20k * 23 chars = 460,000 chars (~115k tokens)
    
    # We construct a state as if Scout just finished, using Pydantic models
    state = {
        "signal": SignalInput(title="Compression Test", source="news"),
        "sentinel_output": SentinelOutput(
            relevance_score=0.9,
            should_investigate=True,
            event_type="product_launch",
            entities=["OpenAI"],
            summary="Large context signal",
            reasoning="N/A"
        ),
        "research_output": ResearchOutput(
            queries_used=["test"],
            results=[],
            key_findings=["Finding A"],
            sources_consulted=10,
            raw_content_summary=massive_content
        ),
        "workflow_id": "test-compress-001",
        "total_tokens_used": 5000,
        "token_budget": TokenBudget(max_tokens=500000).to_dict()
    }
    
    print(f"Calling strategist_node with ~{len(massive_content)//4:,} tokens...")
    # This should trigger 'context_50k_threshold_strategist' in the logs
    result = await strategist_node(state) # type: ignore
    
    if "analysis_output" in result:
        print("SUCCESS: Strategist finished despite massive context.")
    else:
        print(f"FAILURE: Strategist failed. Error: {result.get('error')}")

    print("Check logs for 'context_50k_threshold' events.")
    print("TEST COMPLETE")

async def main():
    configure_logging()
    await test_normal_budget_tracking()
    await test_budget_exhaustion()
    await test_context_compression_trigger()

if __name__ == "__main__":
    asyncio.run(main())
