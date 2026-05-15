"""
ASCENT Verifier Agent — primary source verification.

The Verifier is the step before parallel Scout fan-out. It explicitly
hits primary sources (company blog, PR releases, LinkedIn) to check if a
signal is actually real, or just a hallucinated rumor/leak.

Dev 2 owns this file.
"""
from backend.models.schemas import (
    SignalInput,
    SentinelOutput,
    ActivityEvent,
    AgentStatus,
)
from pydantic import BaseModel, Field
from backend.services.llm import generate_structured
from backend.services.budget import check_budget_or_stop, get_budget
from backend.services.events import publish_event
from backend.services.logger import get_logger
from backend.agents.state import PipelineState
from backend.agents.tools.web_search import search_web

logger = get_logger("verifier")

VERIFIER_SYSTEM_PROMPT = """You are the Verifier — a skeptical but fair competitive intelligence analyst.

You have been given a signal and search results from a quick verification search.
Your job is to determine if this signal is plausible and worth investigating further.

Verification rules:
- If ANY credible source (official blog, PR, news outlet, tech publication) confirms the event → mark as VERIFIED.
- If only unrelated results appear and NOTHING matches the signal at all → mark as UNVERIFIED (likely fabricated).
- If third-party tech sites, forums, or journalists discuss it (even without an official company blog post) → mark as VERIFIED. Real news gets covered by third parties before official blogs.
- Default to VERIFIED when in doubt. The downstream agents will do deeper research.

You are a gate against hallucinated/fabricated signals, NOT a gate against real news that lacks an official press release."""

class VerificationResult(BaseModel):
    is_verified: bool = Field(description="True if explicitly confirmed by primary sources")
    reasoning: str = Field(description="Why you consider it verified or unverified")


async def verifier_node(state: PipelineState) -> dict:
    """
    Verifier agent node for LangGraph.
    Runs a targeted search on primary domains to verify the signal.
    """
    signal: SignalInput = state["signal"]
    sentinel: SentinelOutput = state["sentinel_output"]
    workflow_id = state.get("workflow_id", "unknown")

    wf_logger = logger.with_context(workflow_id=workflow_id)
    wf_logger.info("verifier_started", title=signal.title)

    stopped = check_budget_or_stop(state, "verifier", workflow_id)
    if stopped:
        stopped["budget_exceeded"] = True
        return stopped

    budget = get_budget(state)

    await publish_event("agent_activity", {
        "agent": "verifier",
        "status": "running",
        "message": "Verifying signal against primary sources...",
        "workflow_id": workflow_id,
    })

    # Formulate a verification query based on entities
    entities_str = " ".join(sentinel.entities)
    query = f"{entities_str} {sentinel.event_type} {signal.title} official announcement"

    # Search specifically aiming for high authority domains if possible, or general search
    search_results = await search_web(query, max_results=3, search_depth="basic")

    prompt_parts = [
        f"**Signal Title:** {signal.title}",
        f"**Event Type:** {sentinel.event_type}",
        f"**Entities:** {', '.join(sentinel.entities)}",
        "\n**Primary Source Search Results:**"
    ]

    for res in search_results:
        prompt_parts.append(f"- [{res.title}]({res.url}): {res.snippet}")

    if not search_results:
        prompt_parts.append("NO RESULTS FOUND FROM PRIMARY SEARCH.")

    prompt = "\n".join(prompt_parts)

    try:
        result, _usage = await generate_structured(
            prompt=prompt,
            response_model=VerificationResult,
            system=VERIFIER_SYSTEM_PROMPT,
            temperature=0.1,
            model="llama-3.3-70b-versatile",
            budget=budget,
            agent="verifier",
        )

        wf_logger.info("verifier_completed", is_verified=result.is_verified)

        if not result.is_verified:
            await publish_event("agent_activity", {
                "agent": "verifier",
                "status": "error",
                "message": "Signal debunked/unverified. Halting pipeline.",
                "detail": result.reasoning,
                "workflow_id": workflow_id,
            })
            return {
                "current_agent": "verifier",
                "should_continue": False,
                "error": f"Signal unverified by primary sources: {result.reasoning}",
                **budget.state_updates(),
                "activity_log": [ActivityEvent(
                    agent="verifier",
                    status=AgentStatus.ERROR,
                    message="Signal Unverified",
                    detail=result.reasoning,
                    workflow_id=workflow_id,
                )],
            }

        await publish_event("agent_activity", {
            "agent": "verifier",
            "status": "done",
            "message": "Signal verified as real. Proceeding to deep research.",
            "detail": result.reasoning,
            "workflow_id": workflow_id,
        })

        return {
            "current_agent": "verifier",
            "should_continue": True,
            **budget.state_updates(),
            "activity_log": [ActivityEvent(
                agent="verifier",
                status=AgentStatus.DONE,
                message="Verified from primary sources",
                detail=result.reasoning,
                workflow_id=workflow_id,
            )],
        }

    except Exception as e:
        wf_logger.error("verifier_failed", error=str(e))
        # Fail-open if verification fails
        return {
            "current_agent": "verifier",
            "should_continue": True,
            **budget.state_updates(),
            "activity_log": [ActivityEvent(
                agent="verifier",
                status=AgentStatus.ERROR,
                message=f"Verification tool failed, defaulting to continue. Error: {str(e)[:100]}",
                workflow_id=workflow_id,
            )],
        }
