"""
INFERA Profile Writer — upserts institutional competitor memory after each run.

Dev 2 owns this file. Dev 4 agents produce analysis; this service persists memory.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from backend.models.schemas import (
    AnalysisOutput,
    CompetitorProfile,
    LaunchHistoryEntry,
    ResearchOutput,
    SignalInput,
)
from backend.pipeline.context import get_competitor_profile, upsert_competitor_profile
from backend.integrations.llm import generate_structured
from backend.core.logger import get_logger
from backend.pipeline.context import resolve_competitor_name
from backend.models.schemas import SentinelOutput

logger = get_logger("profile_writer")


class ProfileExtraction(BaseModel):
    """LLM extraction of durable competitor facts from a pipeline run."""
    shipping_record: str = Field(description="One-line pattern of announce vs ship timing")
    launch_history_additions: list[LaunchHistoryEntry] = Field(default_factory=list)
    hiring_signals: list[str] = Field(default_factory=list)
    ceo_public_statements: list[str] = Field(default_factory=list)
    last_assessment: str = Field(description="Updated analyst assessment of this competitor")


PROFILE_SYSTEM = """You extract durable competitive intelligence facts to store as institutional memory.
Focus on: shipping track record, launch delays, hiring signals, CEO statements, and analyst assessment.
Only include facts supported by the provided analysis and research. Be concise."""


async def update_competitor_profile_from_run(
    *,
    signal: SignalInput | None,
    sentinel: SentinelOutput | None,
    analysis: AnalysisOutput | None,
    research_list: list[ResearchOutput] | None,
) -> CompetitorProfile | None:
    """Merge this pipeline run into the competitor profile. Returns updated profile or None."""
    name = resolve_competitor_name(signal, sentinel)
    if not name or not analysis:
        return None

    existing = await get_competitor_profile(name)
    research_summary = ""
    if research_list:
        snippets = []
        for r in research_list[:3]:
            snippets.extend(r.key_findings[:3])
        research_summary = "; ".join(snippets[:12])

    prompt = f"""
Competitor: {name}
Signal: {signal.title if signal else 'Unknown'}

Executive summary: {analysis.executive_summary}
Market impact: {analysis.market_impact[:800]}
Recommendations: {'; '.join(analysis.strategic_recommendations[:5])}

Research highlights: {research_summary[:1500]}

Existing memory:
- Shipping: {existing.shipping_record if existing else 'None'}
- Assessment: {existing.last_assessment if existing else 'None'}

Extract updated institutional memory fields.
"""

    try:
        extracted, _usage = await generate_structured(
            prompt=prompt,
            response_model=ProfileExtraction,
            system=PROFILE_SYSTEM,
            temperature=0.2,
            model="llama-3.3-70b-versatile",
            agent="profile_writer",
        )
    except Exception as e:
        logger.warning("profile_extraction_failed", competitor=name, error=str(e))
        return None

    launch_history = list(existing.launch_history) if existing else []
    seen_products = {e.product.lower() for e in launch_history}
    for entry in extracted.launch_history_additions:
        if entry.product.lower() not in seen_products:
            launch_history.append(entry)
            seen_products.add(entry.product.lower())
    launch_history = launch_history[-10:]

    hiring = list(existing.hiring_signals) if existing else []
    for h in extracted.hiring_signals:
        if h and h not in hiring:
            hiring.append(h)
    hiring = hiring[-8:]

    statements = list(existing.ceo_public_statements) if existing else []
    for s in extracted.ceo_public_statements:
        if s and s not in statements:
            statements.append(s)
    statements = statements[-5:]

    merged = CompetitorProfile(
        competitor_name=name,
        shipping_record=extracted.shipping_record or (existing.shipping_record if existing else ""),
        launch_history=launch_history,
        hiring_signals=hiring,
        ceo_public_statements=statements,
        last_assessment=extracted.last_assessment,
        updated_at=datetime.now(timezone.utc),
    )
    await upsert_competitor_profile(merged)
    logger.info("profile_updated", competitor=name, launches=len(launch_history))
    return merged
