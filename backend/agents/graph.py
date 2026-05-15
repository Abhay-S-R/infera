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
    SentinelOutput,
    ResearchOutput,
    AnalysisOutput,
    ValidationResult,
    ReportOutput,
    AgentStatus,
    ActivityEvent,
)


from backend.agents.strategist import strategist_node
from backend.agents.scribe import scribe_node

# ─── Stub Agent Nodes (will be replaced with real implementations in Phase 1) ───

async def sentinel_node(state: PipelineState) -> dict:
    """
    Monitor agent — filters and classifies incoming signals.
    Stub: passes everything through with high relevance.
    """
    signal = state.get("signal")
    print(f"[Sentinel] Processing signal: {signal.title if signal else 'None'}")

    return {
        "sentinel_output": SentinelOutput(
            relevance_score=0.9,
            should_investigate=True,
            event_type="general",
            entities=[],
            summary=signal.title if signal else "No signal",
            reasoning="Stub: auto-approved for development",
        ),
        "current_agent": "sentinel",
        "activity_log": [ActivityEvent(
            agent="sentinel",
            status=AgentStatus.DONE,
            message="Signal classified",
            detail=f"Relevance: 0.9 (stub)",
        )],
    }


async def scout_node(state: PipelineState) -> dict:
    """
    Research agent — searches the web and gathers evidence.
    Stub: returns empty research output.
    """
    print("[Scout] Researching...")

    return {
        "research_output": ResearchOutput(
            queries_used=["stub query"],
            results=[],
            key_findings=["Stub: no real research performed yet"],
            sources_consulted=0,
            raw_content_summary="Stub research output — will be replaced with real Tavily searches.",
        ),
        "current_agent": "scout",
        "activity_log": [ActivityEvent(
            agent="scout",
            status=AgentStatus.DONE,
            message="Research complete",
            detail="Stub: 0 sources consulted",
        )],
    }



async def arbiter_node(state: PipelineState) -> dict:
    """
    Validator agent — fact-checks analysis against research evidence.
    Stub: auto-approves everything.
    """
    print("[Arbiter] Validating...")

    return {
        "validation_result": ValidationResult(
            is_approved=True,
            overall_confidence=0.8,
            claim_verifications=[],
            issues_found=[],
            suggestions=[],
            retry_with_queries=None,
        ),
        "current_agent": "arbiter",
        "activity_log": [ActivityEvent(
            agent="arbiter",
            status=AgentStatus.DONE,
            message="Validation complete",
            detail="Stub: auto-approved",
        )],
    }



# ─── Routing Logic ───

def should_investigate(state: PipelineState) -> str:
    """After Sentinel: proceed to Scout if signal is worth investigating."""
    sentinel = state.get("sentinel_output")
    if sentinel and sentinel.should_investigate:
        return "scout"
    return "end"


def should_retry_or_proceed(state: PipelineState) -> str:
    """After Arbiter: retry research if validation failed, else proceed to Scribe."""
    validation = state.get("validation_result")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if validation and not validation.is_approved and retry_count < max_retries:
        return "scout"  # Retry with new queries
    return "scribe"     # Proceed to report generation


# ─── Graph Builder ───

def build_graph() -> StateGraph:
    """
    Build and compile the ASCENT agent pipeline graph.

    Returns a compiled LangGraph that can be invoked with:
        result = await graph.ainvoke(initial_state)
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

    # Scout → Strategist (always)
    builder.add_edge("scout", "strategist")

    # Strategist → Arbiter (always)
    builder.add_edge("strategist", "arbiter")

    # Arbiter → conditional: retry or proceed
    builder.add_conditional_edges(
        "arbiter",
        should_retry_or_proceed,
        {
            "scout": "scout",    # Retry loop
            "scribe": "scribe",  # Proceed to report
        },
    )

    # Scribe → END
    builder.add_edge("scribe", END)

    return builder.compile()


# ─── Convenience runner ───

async def run_pipeline(signal: SignalInput, workflow_id: str | None = None) -> PipelineState:
    """
    Run the full ASCENT pipeline for a given signal.

    Args:
        signal: The incoming signal to process
        workflow_id: Optional workflow ID (auto-generated if not provided)

    Returns:
        Final PipelineState with all agent outputs
    """
    if workflow_id is None:
        workflow_id = str(uuid.uuid4())

    graph = build_graph()

    initial_state: PipelineState = {
        "signal": signal,
        "workflow_id": workflow_id,
        "retry_count": 0,
        "max_retries": 3,
        "should_continue": True,
        "current_agent": "sentinel",
        "error": None,
        "activity_log": [],
        "total_tokens_used": 0,
        "total_cost_usd": 0.0,
    }

    result = await graph.ainvoke(initial_state)
    return result
