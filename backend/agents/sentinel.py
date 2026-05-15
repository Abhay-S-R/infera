"""
ASCENT Sentinel Agent — filters and classifies incoming competitive signals.

The Sentinel is the first agent in the pipeline. It receives raw signals
(news articles, webhooks, manual queries) and decides:
  1. How relevant is this signal? (0-1 score)
  2. Should we investigate further? (bool)
  3. What type of event is this? (product launch, funding, etc.)
  4. What entities are involved? (companies, products, people)

Dev 2 owns this file.
"""
from backend.models.schemas import (
    SentinelOutput,
    SignalInput,
    ActivityEvent,
    AgentStatus,
)
from backend.services.llm import generate_structured
from backend.services.budget import BudgetExceededError, check_budget_or_stop, get_budget
from backend.services.events import publish_event
from backend.services.logger import get_logger
from backend.services.tracing import trace_agent
from backend.services.context import competitor_profile_prompt_block
from backend.agents.state import PipelineState

logger = get_logger("sentinel")

SENTINEL_SYSTEM_PROMPT = """You are the Sentinel — the first agent in ASCENT, an autonomous competitive intelligence system.

Your job is to rapidly evaluate incoming signals (news, announcements, events) and determine:
1. **Relevance Score (0-1):** How important is this signal for competitive intelligence?
   - 0.0-0.3: Noise, irrelevant, or trivial
   - 0.4-0.6: Moderately interesting, may warrant a brief look
   - 0.7-0.9: Significant competitive signal, should investigate
   - 0.9-1.0: Critical competitive event, immediate investigation required
2. **Should Investigate:** True if relevance >= 0.5, False otherwise
3. **Event Type:** Classify as one of: product_launch, funding, acquisition, partnership, leadership_change, earnings, regulation, general
4. **Entities:** Extract all companies, products, and key people mentioned
5. **Investigation Angles:** Provide exactly 3 distinct strategic angles to research (e.g., "Financial Impact", "Technical Architecture", "Market Reaction"). Use competitor history to set angles if available (e.g., if they slip launches, add "Delivery credibility").
6. **Summary:** One-paragraph summary of the signal
7. **Reasoning:** Explain WHY you assigned this relevance score
8. **Resolved Competitor:** If a primary competitor company is detected, provide its canonical name here.

Be decisive. Don't hedge. If it's noise, say so. If it's critical, say so."""


@trace_agent("sentinel")
async def sentinel_node(state: PipelineState) -> dict:
    """
    Sentinel agent node for LangGraph.

    Takes the raw signal from state, calls LLM to classify and score it,
    and returns the SentinelOutput to state.
    """
    signal: SignalInput = state["signal"]
    workflow_id = state.get("workflow_id", "unknown")

    wf_logger = logger.with_context(workflow_id=workflow_id)
    wf_logger.info("sentinel_started", title=signal.title, source=signal.source)

    stopped = check_budget_or_stop(state, "sentinel", workflow_id)
    if stopped:
        stopped["budget_exceeded"] = True
        return stopped

    budget = get_budget(state)

    # Publish real-time event for the dashboard
    await publish_event("agent_activity", {
        "agent": "sentinel",
        "status": "running",
        "message": f"Evaluating signal: {signal.title[:80]}",
        "workflow_id": workflow_id,
    })

    # Build the prompt with all available signal data
    prompt_parts = [f"**Signal Title:** {signal.title}"]
    if signal.source:
        prompt_parts.append(f"**Source:** {signal.source}")
    if signal.url:
        prompt_parts.append(f"**URL:** {signal.url}")
    if signal.content:
        prompt_parts.append(f"**Content:**\n{signal.content[:2000]}")
    if signal.competitor_name:
        prompt_parts.append(f"**Known Competitor:** {signal.competitor_name}")
    if signal.custom_question:
        prompt_parts.append(f"**User's Question:** {signal.custom_question}")

    # Inject Institutional Memory
    profile = state.get("competitor_profile")
    if profile:
        mem_block = competitor_profile_prompt_block(profile)
        if mem_block:
            prompt_parts.append(mem_block)

    prompt = (
        "Evaluate the following competitive intelligence signal:\n\n"
        + "\n\n".join(prompt_parts)
        + "\n\nClassify this signal and determine if it warrants deeper investigation."
    )

    try:
        result, _usage = await generate_structured(
            prompt=prompt,
            response_model=SentinelOutput,
            system=SENTINEL_SYSTEM_PROMPT,
            temperature=0.3,  # Low temp for consistent classification
            model="llama-3.3-70b-versatile",
            budget=budget,
            agent="sentinel",
        )

        wf_logger.info(
            "sentinel_completed",
            relevance=result.relevance_score,
            should_investigate=result.should_investigate,
            event_type=result.event_type,
            entities=result.entities,
        )

        # Publish completion event
        await publish_event("agent_activity", {
            "agent": "sentinel",
            "status": "done",
            "message": f"Relevance: {result.relevance_score:.2f} — {'Investigating' if result.should_investigate else 'Skipping'}",
            "detail": result.reasoning[:200],
            "workflow_id": workflow_id,
        })

        return {
            "sentinel_output": result,
            "current_agent": "sentinel",
            "should_continue": result.should_investigate,
            **budget.state_updates(),
            "activity_log": [ActivityEvent(
                agent="sentinel",
                status=AgentStatus.DONE,
                message=f"Signal scored: {result.relevance_score:.2f}",
                detail=result.reasoning[:300],
                workflow_id=workflow_id,
            )],
        }

    except BudgetExceededError as e:
        wf_logger.warning("sentinel_budget_exceeded", error=str(e))
        return {
            **budget.state_updates(),
            "error": str(e),
            "budget_exceeded": True,
            "should_continue": False,
            "current_agent": "sentinel",
            "activity_log": [ActivityEvent(
                agent="sentinel",
                status=AgentStatus.ERROR,
                message="Budget exceeded",
                detail=str(e),
                workflow_id=workflow_id,
            )],
        }

    except Exception as e:
        wf_logger.error("sentinel_failed", error=str(e))

        await publish_event("agent_activity", {
            "agent": "sentinel",
            "status": "error",
            "message": f"Sentinel failed: {str(e)[:100]}",
            "workflow_id": workflow_id,
        })

        # On failure, default to investigating (fail-open)
        return {
            "sentinel_output": SentinelOutput(
                relevance_score=0.7,
                should_investigate=True,
                event_type="general",
                entities=[],
                summary=signal.title,
                reasoning=f"Sentinel LLM call failed ({str(e)[:50]}), defaulting to investigate.",
            ),
            "current_agent": "sentinel",
            "should_continue": True,
            "error": f"Sentinel error: {str(e)}",
            "activity_log": [ActivityEvent(
                agent="sentinel",
                status=AgentStatus.ERROR,
                message=f"Fallback: defaulting to investigate. Error: {str(e)[:100]}",
                workflow_id=workflow_id,
            )],
        }
