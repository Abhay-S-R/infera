"""
ASCENT Agent Graph — LangGraph StateGraph defining the full agent pipeline.

Flow:
  Sentinel → Scout → Strategist → Arbiter → Scribe
                ↑                      |
                └──── retry loop ──────┘

Dev 2 owns this file. Agent implementations are in their own files.
"""
import uuid
from langgraph.graph import StateGraph, END
from backend.agents.state import PipelineState
from backend.models.schemas import (
    SignalInput,
    AnalysisOutput,
    ValidationResult,
    ReportOutput,
    AgentStatus,
    ActivityEvent,
)


from backend.agents.strategist import strategist_node
from backend.agents.scribe import scribe_node
from backend.agents.sentinel import sentinel_node
from backend.agents.scout import scout_node
from backend.agents.arbiter import arbiter_node
from backend.services.budget import TokenBudget


# ─── Routing Logic ───

def _budget_stopped(state: PipelineState) -> bool:
    if state.get("budget_exceeded"):
        return True
    err = state.get("error") or ""
    return "budget exceeded" in err.lower()


def should_investigate(state: PipelineState) -> str:
    """After Sentinel: proceed to Scout if signal is worth investigating."""
    if _budget_stopped(state):
        return "end"
    sentinel = state.get("sentinel_output")
    if sentinel and sentinel.should_investigate:
        return "scout"
    return "end"


def should_retry_or_proceed(state: PipelineState) -> str:
    """After Arbiter: retry research if validation failed, else proceed to Scribe."""
    if _budget_stopped(state):
        return "end"
    validation = state.get("validation_result")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if validation and not validation.is_approved and retry_count < max_retries:
        return "scout"  # Retry with new queries
    return "scribe"     # Proceed to report generation


def should_analyze_or_skip(state: PipelineState) -> str:
    """After Scout: proceed to Strategist if research has data, else skip to Scribe."""
    if _budget_stopped(state):
        return "end"
    research = state.get("research_output")
    if research and research.sources_consulted > 0 and research.key_findings:
        return "strategist"
    # No sources found — skip analysis, let Scribe generate an "insufficient data" report
    return "scribe"


# ─── Graph Builder ───

def build_graph(checkpointer=None):
    """
    Build and compile the ASCENT agent pipeline graph.

    Returns a compiled LangGraph that can be invoked with:
        result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": workflow_id}})
    """
    builder = StateGraph(PipelineState)

    # Add nodes
    builder.add_node("sentinel", sentinel_node)
    builder.add_node("scout", scout_node)
    builder.add_node("strategist", strategist_node)
    builder.add_node("arbiter", arbiter_node)
    builder.add_node("scribe", scribe_node)

    # Set entry point
    builder.set_entry_point("sentinel")

    # Sentinel → conditional: investigate or skip
    builder.add_conditional_edges(
        "sentinel",
        should_investigate,
        {
            "scout": "scout",
            "end": END,
        },
    )

    # Scout → conditional: analyze if we have data, else skip to report
    builder.add_conditional_edges(
        "scout",
        should_analyze_or_skip,
        {
            "strategist": "strategist",  # Has research data
            "scribe": "scribe",          # No sources → "insufficient data" report
            "end": END,
        },
    )

    # Strategist → Arbiter (always)
    builder.add_edge("strategist", "arbiter")

    # Arbiter → conditional: retry or proceed
    builder.add_conditional_edges(
        "arbiter",
        should_retry_or_proceed,
        {
            "scout": "scout",    # Retry loop
            "scribe": "scribe",  # Proceed to report
            "end": END,
        },
    )

    # Scribe → END
    builder.add_edge("scribe", END)

    return builder.compile(checkpointer=checkpointer)


def pipeline_config(workflow_id: str) -> dict:
    """LangGraph config for checkpointing — thread_id maps to workflow id."""
    return {"configurable": {"thread_id": workflow_id}}


# ─── Convenience runner ───

async def run_pipeline(
    signal: SignalInput | None = None,
    workflow_id: str | None = None,
    checkpointer=None,
    *,
    resume: bool = False,
) -> PipelineState:
    """
    Run the full ASCENT pipeline for a given signal.

    Args:
        signal: The incoming signal to process (not required when resume=True)
        workflow_id: Workflow / checkpoint thread id (auto-generated if not provided)
        checkpointer: LangGraph PostgresSaver for crash recovery
        resume: If True, continue from the last checkpointed agent

    Returns:
        Final PipelineState with all agent outputs
    """
    if workflow_id is None:
        workflow_id = str(uuid.uuid4())

    graph = build_graph(checkpointer=checkpointer)
    config = pipeline_config(workflow_id)

    if resume:
        result = await graph.ainvoke(None, config=config)
        return result

    if signal is None:
        raise ValueError("signal is required when resume=False")

    budget = TokenBudget()
    initial_state: PipelineState = {
        "signal": signal,
        "workflow_id": workflow_id,
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

    result = await graph.ainvoke(initial_state, config=config)
    return result
