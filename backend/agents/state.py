"""
ASCENT Pipeline State — the shared state that flows through all agents in the LangGraph.
This is the single source of truth for what data moves between agents.

Dev 2 owns this file. Other devs: import from here, never define your own state.
"""
from typing import Optional, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from backend.models.schemas import (
    SignalInput,
    SentinelOutput,
    VerificationOutput,
    CompetitorProfile,
    ResearchOutput,
    AnalysisOutput,
    ValidationResult,
    ReportOutput,
    ActivityEvent,
)


def _replace(existing, new):
    """Reducer that replaces the old value with the new one."""
    return new


def _append_list(existing, new):
    """Reducer that appends new items to an existing list."""
    if existing is None:
        existing = []
    if isinstance(new, list):
        return existing + new
    return existing + [new]


class PipelineState(TypedDict, total=False):
    """
    Shared state for the entire ASCENT agent pipeline.

    Each agent reads what it needs and writes its output.
    Annotated fields use reducers so parallel updates merge correctly.
    """

    # ─── Input (set once at pipeline start) ───
    signal: SignalInput                                         # Raw incoming signal
    workflow_id: str                                            # Unique ID for this pipeline run

    # ─── Sentinel output ───
    sentinel_output: Annotated[Optional[SentinelOutput], _replace]

    # ─── Verifier output (Phase 4) ───
    verification_output: Annotated[Optional[VerificationOutput], _replace]

    # ─── Competitor institutional memory (Phase 4) ───
    competitor_profile: Annotated[Optional[CompetitorProfile], _replace]

    # ─── Scout output (List for parallel fan-out) ───
    research_output: Annotated[list[ResearchOutput], _append_list]

    # ─── Strategist output ───
    analysis_output: Annotated[Optional[AnalysisOutput], _replace]

    # ─── Arbiter output ───
    validation_result: Annotated[Optional[ValidationResult], _replace]

    # ─── Scribe output ───
    report_output: Annotated[Optional[ReportOutput], _replace]

    # ─── Control flow ───
    retry_count: Annotated[int, _replace]                       # How many times we've retried research
    max_retries: Annotated[int, _replace]                       # Max retry limit (default 3)
    should_continue: Annotated[bool, _replace]                  # Whether pipeline should proceed
    current_agent: Annotated[str, _replace]                     # Which agent is currently running
    current_angle: Annotated[Optional[str], _replace]           # The specific angle this scout is researching
    error: Annotated[Optional[str], _replace]                   # Error message if something failed

    # ─── Activity log ───
    activity_log: Annotated[list[ActivityEvent], _append_list]  # All events for the WebSocket feed

    # ─── Budget tracking (Dev 4) ───
    token_budget: Annotated[Optional[dict], _replace]  # Serialized TokenBudget
    total_tokens_used: Annotated[int, _replace]
    total_cost_usd: Annotated[float, _replace]
    budget_exceeded: Annotated[bool, _replace]
