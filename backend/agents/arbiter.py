"""
ASCENT Arbiter Agent — validates analysis against research evidence.

The Arbiter cross-references claims in the Strategist's AnalysisOutput
against the Scout's ResearchOutput. If confidence is too low, it sends
the pipeline back to Scout with modified search queries (semantic retry).

Dev 2 owns this file.
"""
from backend.models.schemas import (
    ValidationResult,
    AnalysisOutput,
    ResearchOutput,
    ActivityEvent,
    AgentStatus,
)
from backend.services.llm import generate_structured
from backend.services.budget import check_budget_or_stop, get_budget
from backend.services.events import publish_event
from backend.services.logger import get_logger
from backend.agents.state import PipelineState
from backend.services.tracing import trace_agent

logger = get_logger("arbiter")

ARBITER_SYSTEM_PROMPT = """You are the Arbiter — the quality-control agent in ASCENT, an autonomous competitive intelligence system.

## Your Mission
Cross-reference every major claim in the Strategist's analysis against the Scout's research evidence. Produce a clear approve/reject decision.

## Verification Process
1. **Enumerate claims:** Extract each factual assertion from the executive summary, market impact, and insights sections.
2. **Evidence check:** For each claim, look for supporting data in the research key_findings and raw_content_summary. Mark as:
   - ✅ VERIFIED — directly supported by evidence
   - ⚠️ PARTIAL — related evidence exists but doesn't fully confirm
   - ❌ UNVERIFIED — no supporting evidence found
3. **Score:** `overall_confidence` = proportion of verified + 0.5 × partial claims.

## Decision Rules
- **APPROVE** (`is_approved = true`) if overall_confidence ≥ 0.55
- **REJECT** (`is_approved = false`) if overall_confidence < 0.55 AND retry could help (i.e. the gaps are researchable)
- When rejecting, provide exactly 2-3 NEW search queries in `retry_with_queries` that target the SPECIFIC evidence gaps. These must differ from the original queries.
- Always list specific issues in `issues_found` (even when approving).

## Important
- Do NOT reject just because minor details lack citations. Focus on core claims.
- If the analysis relies primarily on unverified rumors, leaks, or speculation without hard evidence from Scout, you MUST REJECT IT (`is_approved = false`) and request specific queries to find official verification.
- `claim_verifications` should contain a brief note per claim: "Claim X: verified/partial/unverified".
- `suggestions` should contain actionable improvements for the next report iteration."""


@trace_agent("arbiter")
async def arbiter_node(state: PipelineState) -> dict:
    """
    Arbiter agent node for LangGraph.

    Cross-references AnalysisOutput against ResearchOutput,
    decides approve/reject, and provides retry queries if needed.
    """
    analysis: AnalysisOutput = state.get("analysis_output")
    research_list: list[ResearchOutput] = state.get("research_output", [])
    signal = state.get("signal")
    workflow_id = state.get("workflow_id", "unknown")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    wf_logger = logger.with_context(workflow_id=workflow_id, retry=retry_count)
    wf_logger.info("arbiter_started")

    stopped = check_budget_or_stop(state, "arbiter", workflow_id)
    if stopped:
        stopped["budget_exceeded"] = True
        return stopped

    budget = get_budget(state)

    await publish_event("agent_activity", {
        "agent": "arbiter",
        "status": "running",
        "message": f"Validating analysis (attempt {retry_count + 1}/{max_retries + 1})",
        "workflow_id": workflow_id,
    })

    # If no analysis exists (strategist failed), auto-approve with low confidence
    if not analysis:
        wf_logger.warning("arbiter_no_analysis", reason="Missing analysis_output")
        return _auto_approve(workflow_id, confidence=0.3, reason="No analysis to validate")

    # On final retry, auto-approve to prevent infinite loops
    if retry_count >= max_retries:
        wf_logger.info("arbiter_max_retries", retry_count=retry_count)
        return _auto_approve(
            workflow_id,
            confidence=0.5,
            reason=f"Auto-approved after {retry_count} retries to prevent infinite loop",
        )

    # Build the validation prompt
    prompt = _build_validation_prompt(signal, analysis, research_list)

    try:
        result, _usage = await generate_structured(
            prompt=prompt,
            response_model=ValidationResult,
            system=ARBITER_SYSTEM_PROMPT,
            temperature=0.2,  # Very low temp for consistent validation
            max_output_tokens=8192,
            model="llama-3.3-70b-versatile",  # Fast validation via Groq
            budget=budget,
            agent="arbiter",
        )

        wf_logger.info(
            "arbiter_completed",
            is_approved=result.is_approved,
            confidence=result.overall_confidence,
            issues=len(result.issues_found),
            has_retry_queries=result.retry_with_queries is not None,
        )

        # Determine status message
        if result.is_approved:
            status_msg = f"Approved (confidence: {result.overall_confidence:.2f})"
        else:
            retry_info = f" — retrying with new queries" if result.retry_with_queries else ""
            status_msg = f"Rejected (confidence: {result.overall_confidence:.2f}){retry_info}"

        await publish_event("agent_activity", {
            "agent": "arbiter",
            "status": "done" if result.is_approved else "retry",
            "message": status_msg,
            "detail": "; ".join(result.issues_found[:3]) if result.issues_found else "All claims verified",
            "workflow_id": workflow_id,
        })

        if not result.is_approved:
            await publish_event("arbiter.rejected", {
                "agent": "arbiter",
                "status": "rejected",
                "message": status_msg,
                "detail": "; ".join(result.issues_found[:5]) if result.issues_found else "Validation failed",
                "confidence": result.overall_confidence,
                "retry_queries": result.retry_with_queries or [],
                "workflow_id": workflow_id,
            })

        return {
            "validation_result": result,
            "current_agent": "arbiter",
            "retry_count": retry_count + 1 if not result.is_approved else retry_count,
            **budget.state_updates(),
            "activity_log": [ActivityEvent(
                agent="arbiter",
                status=AgentStatus.DONE,
                message=status_msg,
                detail=f"Issues: {result.issues_found[:2]}" if result.issues_found else "Clean validation",
                workflow_id=workflow_id,
            )],
        }

    except Exception as e:
        wf_logger.error("arbiter_failed", error=str(e))

        await publish_event("agent_activity", {
            "agent": "arbiter",
            "status": "error",
            "message": f"Arbiter error: {str(e)[:100]}",
            "workflow_id": workflow_id,
        })

        # On error, auto-approve to keep pipeline moving
        return _auto_approve(workflow_id, confidence=0.4, reason=f"Validation failed: {str(e)[:100]}")


def _auto_approve(workflow_id: str, confidence: float, reason: str) -> dict:
    """Generate an auto-approved ValidationResult."""
    return {
        "validation_result": ValidationResult(
            is_approved=True,
            overall_confidence=confidence,
            claim_verifications=[],
            issues_found=[reason],
            suggestions=[],
            retry_with_queries=None,
        ),
        "current_agent": "arbiter",
        "activity_log": [ActivityEvent(
            agent="arbiter",
            status=AgentStatus.DONE,
            message=f"Auto-approved: {reason}",
            workflow_id=workflow_id,
        )],
    }


def _build_validation_prompt(signal, analysis: AnalysisOutput, research_list: list[ResearchOutput]) -> str:
    """Build the validation prompt from analysis and research."""
    prompt = f"## Signal\n**Title:** {signal.title if signal else 'Unknown'}\n\n"

    prompt += "## Analysis to Validate\n"
    prompt += f"**Executive Summary:** {analysis.executive_summary}\n"
    prompt += f"**Market Impact:** {analysis.market_impact}\n"
    prompt += f"**Competitive Positioning:** {analysis.competitive_positioning}\n"

    if analysis.insights:
        prompt += "\n**Insights:**\n"
        for i in analysis.insights:
            prompt += f"- {i.insight} (Impact: {i.impact})\n"

    if analysis.strategic_recommendations:
        prompt += "\n**Recommendations:**\n"
        for r in analysis.strategic_recommendations:
            prompt += f"- {r}\n"

    prompt += f"\n**Stated Confidence:** {analysis.overall_confidence}\n"

    prompt += "\n## Research Evidence (Scout's Findings from Multiple Angles)\n"
    if research_list:
        all_queries = []
        for idx, research in enumerate(research_list):
            prompt += f"\n### Research Angle {idx + 1}\n"
            if research.key_findings:
                prompt += "**Key Findings:**\n"
                for f in research.key_findings:
                    prompt += f"- {f}\n"
            if research.raw_content_summary:
                prompt += f"\n**Raw Summary:** {research.raw_content_summary[:1000]}\n"
            all_queries.extend(research.queries_used)
        if all_queries:
            prompt += f"\n**Original Search Queries:** {all_queries}\n"
    else:
        prompt += "No research findings available.\n"

    prompt += (
        "\n## Your Task\n"
        "1. Verify each major claim in the analysis against the research evidence\n"
        "2. Score overall confidence based on evidence support\n"
        "3. If rejecting, provide 2-3 NEW search queries targeting the evidence gaps\n"
        "   (these must be DIFFERENT from the original queries listed above)\n"
    )

    return prompt
