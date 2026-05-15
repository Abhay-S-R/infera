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
from langgraph.constants import Send
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
from backend.agents.verifier import verifier_node
from backend.services.budget import TokenBudget


# ─── Routing Logic ───

def _budget_stopped(state: PipelineState) -> bool:
    if state.get("budget_exceeded"):
        return True
    err = state.get("error") or ""
    return "budget exceeded" in err.lower()


def should_verify(state: PipelineState) -> str:
    """After Sentinel: proceed to Verifier if signal is worth investigating."""
    if _budget_stopped(state):
        return "end"
    sentinel = state.get("sentinel_output")
    if sentinel and sentinel.should_investigate:
        return "verifier"
    return "end"


def should_continue_to_scouts(state: PipelineState):
    """After Verifier: If verified, fan out to parallel scouts."""
    if _budget_stopped(state) or not state.get("should_continue", True):
        return ["__end__"]
        
    sentinel = state.get("sentinel_output")
    if not sentinel:
        return ["__end__"]
        
    angles = sentinel.investigation_angles or ["General Investigation"]
    if not angles:
        angles = ["General Investigation"]
        
    # Map-Reduce: Spawn a scout node for each angle
    sends = []
    for angle in angles:
        scout_state = dict(state)
        scout_state["current_angle"] = angle
        sends.append(Send("scout", scout_state))
        
    return sends


def should_retry_or_proceed(state: PipelineState):
    """After Arbiter: retry research if validation failed, else proceed to Scribe."""
    if _budget_stopped(state):
        return "__end__"
    validation = state.get("validation_result")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if validation and not validation.is_approved and retry_count < max_retries:
        # Spawn a single targeted retry scout
        scout_state = dict(state)
        scout_state["current_angle"] = "Targeted Retry"
        return [Send("scout", scout_state)]
        
    return "scribe"


def should_analyze_or_skip(state: PipelineState) -> str:
    """After Scout: proceed to Strategist if any research has data, else skip to Scribe."""
    if _budget_stopped(state):
        return "__end__"
    research_list = state.get("research_output", [])
    
    # Check if ANY scout found data
    has_data = any(r.sources_consulted > 0 and r.key_findings for r in research_list)
    if has_data:
        return "strategist"
    # No sources found — skip analysis
    return "scribe"


# ─── Graph Builder ───

def build_graph(checkpointer=None, *, interrupt_before: list[str] | None = None):
    """
    Build and compile the ASCENT agent pipeline graph.
    """
    builder = StateGraph(PipelineState)

    # Add nodes
    builder.add_node("sentinel", sentinel_node)
    builder.add_node("verifier", verifier_node)
    builder.add_node("scout", scout_node)
    builder.add_node("strategist", strategist_node)
    builder.add_node("arbiter", arbiter_node)
    builder.add_node("scribe", scribe_node)

    # Set entry point
    builder.set_entry_point("sentinel")

    # Sentinel → Verifier or END
    builder.add_conditional_edges(
        "sentinel",
        should_verify,
        {
            "verifier": "verifier",
            "end": END,
        },
    )

    # Verifier → Fan-out to Scouts or END
    builder.add_conditional_edges(
        "verifier",
        should_continue_to_scouts,
        ["scout", "__end__"]
    )

    # Scout → Strategist or Scribe
    builder.add_conditional_edges(
        "scout",
        should_analyze_or_skip,
        {
            "strategist": "strategist",
            "scribe": "scribe",
            "__end__": END,
        },
    )

    # Strategist → Arbiter (always)
    builder.add_edge("strategist", "arbiter")

    # Arbiter → Retry (Scout) or Scribe
    builder.add_conditional_edges(
        "arbiter",
        should_retry_or_proceed,
        ["scout", "scribe", "__end__"]
    )

    # Scribe → END
    builder.add_edge("scribe", END)

    compile_kwargs: dict = {"checkpointer": checkpointer}
    if interrupt_before:
        compile_kwargs["interrupt_before"] = interrupt_before
    return builder.compile(**compile_kwargs)


def pipeline_config(workflow_id: str) -> dict:
    """LangGraph config for checkpointing — thread_id maps to workflow id."""
    return {"configurable": {"thread_id": workflow_id}}


async def get_checkpoint_next_agent(workflow_id: str, checkpointer) -> str | None:
    """Return the next agent node from the LangGraph checkpoint (for resume UX/logging)."""
    graph = build_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state(pipeline_config(workflow_id))
    if snapshot and snapshot.next:
        node = snapshot.next[0]
        if isinstance(node, str):
            return node
        return str(node)
    return None


# ─── Convenience runner ───

async def run_pipeline(
    signal: SignalInput | None = None,
    workflow_id: str | None = None,
    checkpointer=None,
    *,
    resume: bool = False,
    initial_state: PipelineState | None = None,
) -> PipelineState:
    """
    Run the full ASCENT pipeline for a given signal.

    Args:
        signal: The incoming signal to process (not required when resume=True)
        workflow_id: Workflow / checkpoint thread id (auto-generated if not provided)
        checkpointer: LangGraph PostgresSaver for crash recovery
        resume: If True, continue from the last checkpointed agent
        initial_state: Optional dict to override default starting state (for testing)

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

    if signal is None and not (initial_state and "signal" in initial_state):
        raise ValueError("signal is required when resume=False")

    budget = TokenBudget()
    default_state: PipelineState = {
        "signal": signal,  # type: ignore[typeddict-item]
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
    
    # Merge initial_state into defaults
    final_initial_state = default_state.copy()
    if initial_state:
        final_initial_state.update(initial_state)

    result = await graph.ainvoke(final_initial_state, config=config)
    return result
