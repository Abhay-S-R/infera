"""
ASCENT Profile Loader — loads institutional memory after Sentinel resolves competitor.

Runs between Sentinel and Verifier so Dev 4 can set resolved_competitor without
touching graph wiring.
"""
from backend.agents.state import PipelineState
from backend.models.schemas import ActivityEvent, AgentStatus, SignalInput
from backend.pipeline.context import (
    competitor_profile_prompt_block,
    load_competitor_profile_for_pipeline,
    resolve_competitor_name,
)
from backend.core.logger import get_logger
from backend.core.tracing import trace_agent

logger = get_logger("profile_loader")


@trace_agent("profile_loader")
async def profile_loader_node(state: PipelineState) -> dict:
    """Load competitor profile into state if not already present."""
    workflow_id = state.get("workflow_id", "unknown")
    signal: SignalInput = state["signal"]
    sentinel = state.get("sentinel_output")
    existing = state.get("competitor_profile")

    if existing is not None:
        return {
            "current_agent": "profile_loader",
            "activity_log": [
                ActivityEvent(
                    agent="profile_loader",
                    status=AgentStatus.DONE,
                    message=f"Profile already loaded: {existing.competitor_name}",
                    workflow_id=workflow_id,
                )
            ],
        }

    profile = await load_competitor_profile_for_pipeline(signal, sentinel)
    name = resolve_competitor_name(signal, sentinel)

    if profile:
        logger.info(
            "profile_loaded",
            workflow_id=workflow_id,
            competitor=profile.competitor_name,
            launches=len(profile.launch_history),
        )
        ctx_block = competitor_profile_prompt_block(profile)
        return {
            "competitor_profile": profile,
            "competitor_context": ctx_block or None,
            "current_agent": "profile_loader",
            "activity_log": [
                ActivityEvent(
                    agent="profile_loader",
                    status=AgentStatus.DONE,
                    message=f"Loaded memory for {profile.competitor_name}",
                    detail=f"{len(profile.launch_history)} past launches on record",
                    workflow_id=workflow_id,
                )
            ],
        }

    return {
        "current_agent": "profile_loader",
        "activity_log": [
            ActivityEvent(
                agent="profile_loader",
                status=AgentStatus.SKIPPED,
                message=f"No institutional memory for {name or 'unknown competitor'}",
                workflow_id=workflow_id,
            )
        ],
    }
