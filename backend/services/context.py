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

# Phase 2b: compress when estimated pipeline state exceeds this (chars / 4 heuristic)
STATE_TOKEN_THRESHOLD = 50_000
SUMMARY_MAX_CHARS = 2_000
_CHARS_PER_TOKEN = 4


def estimate_state_tokens(state: PipelineState) -> int:
    """Rough token estimate for all major fields in pipeline state."""
    total_chars = 0

    signal = state.get("signal")
    if signal:
        total_chars += len(signal.title) + len(signal.source or "")
        total_chars += len(signal.content or "")
        total_chars += len(signal.competitor_name or "")
        total_chars += len(signal.custom_question or "")

    sentinel = state.get("sentinel_output")
    if sentinel:
        total_chars += len(sentinel.summary) + len(sentinel.reasoning)
        total_chars += sum(len(e) for e in sentinel.entities)

    research = state.get("research_output")
    if research:
        total_chars += _research_char_count(research)

    analysis = state.get("analysis_output")
    if analysis:
        total_chars += _analysis_char_count(analysis)

    validation = state.get("validation_result")
    if validation:
        total_chars += len(" ".join(validation.issues_found))
        total_chars += len(" ".join(validation.suggestions or []))

    return max(1, total_chars // _CHARS_PER_TOKEN)


def _research_char_count(research: ResearchOutput) -> int:
    n = len(research.raw_content_summary)
    n += sum(len(f) for f in research.key_findings)
    n += sum(len(q) for q in research.queries_used)
    for r in research.results:
        n += len(r.title) + len(r.snippet) + len(r.url)
    return n


def _analysis_char_count(analysis: AnalysisOutput) -> int:
    n = (
        len(analysis.executive_summary)
        + len(analysis.market_impact)
        + len(analysis.competitive_positioning)
    )
    n += sum(len(i.insight) + len(i.impact) for i in analysis.insights)
    n += sum(len(r) for r in analysis.strategic_recommendations)
    return n


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


async def compress_research_output(
    research: ResearchOutput,
    budget: TokenBudget,
    *,
    max_chars: int = SUMMARY_MAX_CHARS,
) -> ResearchOutput:
    """LLM-summarize research to fit within max_chars (Phase 2b)."""
    wf_log = logger
    if len(research.raw_content_summary) <= max_chars and _research_char_count(research) <= max_chars * 2:
        return research

    source_text = (
        f"Key findings:\n"
        + "\n".join(f"- {f}" for f in research.key_findings[:15])
        + f"\n\nFull summary:\n{research.raw_content_summary[:15000]}"
    )
    prompt = (
        f"Compress this competitive research into at most {max_chars} characters. "
        "Keep facts, numbers, company names, and dates. Output plain text only.\n\n"
        f"{source_text}"
    )
    try:
        text, _usage = await generate(
            prompt=prompt,
            system="You are a concise intelligence editor. Never exceed the character limit.",
            model=SUMMARY_MODEL,
            temperature=0.2,
            max_output_tokens=1024,
            budget=budget,
            agent="context",
        )
        summary = text.strip()[:max_chars]
    except Exception as e:
        wf_log.warning("context_research_compress_fallback", error=str(e))
        summary = research.raw_content_summary[:max_chars]

    findings = research.key_findings[:5]
    if summary and summary not in findings:
        findings = [summary[:500]] + findings

    logger.info("context_research_compressed", max_chars=max_chars, summary_len=len(summary))
    return ResearchOutput(
        queries_used=research.queries_used[:5],
        results=research.results[:5],
        key_findings=findings,
        sources_consulted=research.sources_consulted,
        raw_content_summary=summary,
    )


async def compress_analysis_output(
    analysis: AnalysisOutput,
    budget: TokenBudget,
    *,
    max_chars: int = SUMMARY_MAX_CHARS,
) -> AnalysisOutput:
    """LLM-summarize analysis before Scribe when state is large (Phase 2b)."""
    full_text = (
        f"{analysis.executive_summary}\n{analysis.market_impact}\n"
        f"{analysis.competitive_positioning}\n"
        + "\n".join(f"- {i.insight}" for i in analysis.insights)
        + "\n"
        + "\n".join(f"- {r}" for r in analysis.strategic_recommendations)
    )
    if len(full_text) <= max_chars:
        return analysis

    prompt = (
        f"Compress this competitive analysis into at most {max_chars} characters "
        "for a report writer. Preserve key conclusions and recommendations.\n\n"
        f"{full_text[:15000]}"
    )
    try:
        text, _usage = await generate(
            prompt=prompt,
            system="You are a concise intelligence editor. Never exceed the character limit.",
            model=SUMMARY_MODEL,
            temperature=0.2,
            max_output_tokens=1024,
            budget=budget,
            agent="context",
        )
        summary = text.strip()[:max_chars]
    except Exception as e:
        logger.warning("context_analysis_compress_fallback", error=str(e))
        summary = analysis.executive_summary[:max_chars]

    logger.info("context_analysis_compressed", max_chars=max_chars, summary_len=len(summary))
    return AnalysisOutput(
        executive_summary=summary,
        market_impact=summary,
        competitive_positioning="See executive summary.",
        insights=analysis.insights[:3],
        strategic_recommendations=analysis.strategic_recommendations[:5],
        overall_confidence=analysis.overall_confidence,
    )


async def prepare_for_strategist(
    state: PipelineState,
    budget: TokenBudget,
) -> tuple[PipelineState, Optional[ResearchOutput], int]:
    """
    Apply tiered budget compression, then Phase 2b 50k-token research compression.
    Returns (context state, research for prompts, estimated tokens after tier pass).
    """
    ctx = await summarize_for_next_agent(state, "strategist", budget=budget)
    estimated = estimate_state_tokens(ctx)
    research = ctx.get("research_output") or state.get("research_output")

    if estimated > STATE_TOKEN_THRESHOLD and research:
        logger.info(
            "context_50k_threshold_strategist",
            estimated_tokens=estimated,
            threshold=STATE_TOKEN_THRESHOLD,
        )
        compressed = await compress_research_output(research, budget)
        ctx = copy.copy(dict(ctx))
        ctx["research_output"] = compressed
        estimated = estimate_state_tokens(ctx)  # type: ignore[arg-type]

    research_out = ctx.get("research_output") or research
    return ctx, research_out, estimated


async def prepare_for_scribe(
    state: PipelineState,
    budget: TokenBudget,
) -> tuple[PipelineState, Optional[AnalysisOutput], Optional[ResearchOutput], int]:
    """Tiered compression + 50k analysis compression before Scribe."""
    ctx = await summarize_for_next_agent(state, "scribe", budget=budget)
    estimated = estimate_state_tokens(ctx)
    analysis = ctx.get("analysis_output") or state.get("analysis_output")
    research = ctx.get("research_output") or state.get("research_output")

    if estimated > STATE_TOKEN_THRESHOLD and analysis:
        logger.info(
            "context_50k_threshold_scribe",
            estimated_tokens=estimated,
            threshold=STATE_TOKEN_THRESHOLD,
        )
        compressed = await compress_analysis_output(analysis, budget)
        ctx = copy.copy(dict(ctx))
        ctx["analysis_output"] = compressed
        estimated = estimate_state_tokens(ctx)  # type: ignore[arg-type]
        analysis = compressed

    return ctx, analysis, research, estimated


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
