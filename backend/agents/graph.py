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

# ─── Real Agent Imports (Phase 1) ───
from backend.agents.sentinel import sentinel_node
from backend.agents.scout import scout_node


async def strategist_node(state: PipelineState) -> dict:
    """
    Analysis agent — synthesizes research into competitive analysis.
    Stub: returns placeholder analysis.
    """
    print("[Strategist] Analyzing...")

    return {
        "analysis_output": AnalysisOutput(
            executive_summary="Stub analysis — will be replaced with real LLM reasoning.",
            market_impact="Stub: unknown impact",
            competitive_positioning="Stub: unknown positioning",
            insights=[],
            strategic_recommendations=["Stub: implement real analysis"],
            overall_confidence=0.5,
        ),
        "current_agent": "strategist",
        "activity_log": [ActivityEvent(
            agent="strategist",
            status=AgentStatus.DONE,
            message="Analysis complete",
            detail="Stub: placeholder analysis",
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


async def scribe_node(state: PipelineState) -> dict:
    """
    Report agent — generates the final deliverable.
    Stub: returns a placeholder report.
    """
    signal = state.get("signal")
    print("[Scribe] Generating report...")

    return {
        "report_output": ReportOutput(
            title=f"Intelligence Report: {signal.title if signal else 'Unknown'}",
            executive_summary="Stub report — pipeline is wired correctly.",
            full_report_markdown="# Stub Report\n\nThe pipeline ran end-to-end. Replace stubs with real agents.",
            confidence_score=0.5,
            sources=[],
        ),
        "current_agent": "scribe",
        "activity_log": [ActivityEvent(
            agent="scribe",
            status=AgentStatus.DONE,
            message="Report generated",
            detail="Stub: placeholder report",
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
