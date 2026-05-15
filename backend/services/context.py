"""
ASCENT Tiered Context Manager — compresses prior agent outputs by budget tier.

Dev 4 owns this file.
"""
from __future__ import annotations

import copy
from typing import Any, Optional

from backend.agents.state import PipelineState
from backend.models.schemas import (
    AnalysisOutput,
    ResearchOutput,
    SentinelOutput,
)
from backend.services.budget import TokenBudget, get_budget
from backend.services.llm import generate
from backend.services.logger import get_logger

logger = get_logger("context")

SUMMARY_MODEL = "llama-3.3-70b-versatile"


async def summarize_for_next_agent(
    state: PipelineState,
    target_agent: str,
    budget: Optional[TokenBudget] = None,
) -> PipelineState:
    """
    Return a shallow copy of state with prior outputs compressed per budget tier.

    Tier 1 (< 50% budget): full state
    Tier 2 (50–80%): research → key findings only
    Tier 3 (> 80%): one-paragraph summary of everything relevant to target_agent
    """
    budget = budget or get_budget(state)
    tier = budget.tier()

    if tier == 1:
        return state

    compressed = copy.copy(dict(state))
    wf_id = state.get("workflow_id", "unknown")
    log = logger.with_context(workflow_id=wf_id, target_agent=target_agent, tier=tier)

    research: Optional[ResearchOutput] = state.get("research_output")
    analysis: Optional[AnalysisOutput] = state.get("analysis_output")
    sentinel: Optional[SentinelOutput] = state.get("sentinel_output")

    if tier == 2 and research:
        log.info("context_tier2_research_compression")
        compressed["research_output"] = ResearchOutput(
            queries_used=research.queries_used[:5],
            results=research.results[:5],
            key_findings=research.key_findings,
            sources_consulted=research.sources_consulted,
            raw_content_summary=research.raw_content_summary[:4000],
        )
        return compressed  # type: ignore[return-value]

    # Tier 3: aggressive one-paragraph summary
    log.info("context_tier3_full_compression")
    summary_text = await _build_tier3_summary(
        target_agent=target_agent,
        sentinel=sentinel,
        research=research,
        analysis=analysis,
        budget=budget,
    )

    if research and target_agent in ("strategist", "arbiter"):
        compressed["research_output"] = ResearchOutput(
            queries_used=research.queries_used[:3],
            results=[],
            key_findings=[summary_text],
            sources_consulted=research.sources_consulted,
            raw_content_summary=summary_text,
        )

    if analysis and target_agent == "scribe":
        compressed["analysis_output"] = AnalysisOutput(
            executive_summary=summary_text,
            market_impact=summary_text,
            competitive_positioning="See executive summary.",
            insights=analysis.insights[:3],
            strategic_recommendations=analysis.strategic_recommendations[:5],
            overall_confidence=analysis.overall_confidence,
        )

    return compressed  # type: ignore[return-value]


async def _build_tier3_summary(
    *,
    target_agent: str,
    sentinel: Optional[SentinelOutput],
    research: Optional[ResearchOutput],
    analysis: Optional[AnalysisOutput],
    budget: TokenBudget,
) -> str:
    """One-paragraph summary for tier-3 context passing."""
    parts: list[str] = []
    if sentinel:
        parts.append(f"Signal: {sentinel.summary} (relevance {sentinel.relevance_score:.2f})")
    if research and research.key_findings:
        parts.append("Findings: " + "; ".join(research.key_findings[:8]))
    if analysis:
        parts.append(f"Analysis: {analysis.executive_summary}")

    combined = "\n".join(parts)
    if len(combined) < 800:
        return combined

    prompt = (
        f"Compress the following competitive intelligence context into ONE dense paragraph "
        f"for the {target_agent} agent. Keep facts, numbers, and entity names.\n\n"
        f"{combined[:12000]}"
    )
    try:
        text, _usage = await generate(
            prompt=prompt,
            system="You compress text without losing critical facts. Output a single paragraph only.",
            model=SUMMARY_MODEL,
            temperature=0.2,
            max_output_tokens=512,
            budget=budget,
            agent="context",
        )
        return text.strip() or combined[:1500]
    except Exception as e:
        logger.warning("context_tier3_llm_fallback", error=str(e))
        return combined[:1500]


def research_prompt_block(research: ResearchOutput, *, tier: int) -> str:
    """Format research for agent prompts based on compression tier."""
    if tier >= 3:
        return f"Research (compressed):\n{research.raw_content_summary}\n"
    if tier == 2:
        findings = "\n".join(f"- {f}" for f in research.key_findings)
        return f"Key Findings:\n{findings}\n\nSummary:\n{research.raw_content_summary[:2000]}\n"
    findings = "\n".join(f"- {f}" for f in research.key_findings)
    return (
        f"Key Findings:\n{findings}\n\n"
        f"Raw Content Summary:\n{research.raw_content_summary}\n"
    )
