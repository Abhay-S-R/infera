"""
ASCENT Verifier Agent — skeptical primary-source verification (Phase 4).

Runs multi-step checks before Scout fan-out: signal URL, official blog,
product/pricing page, LinkedIn, optional SEC. Fail-closed on fabricated signals.
"""
from __future__ import annotations

import re

from backend.config import settings
from backend.models.schemas import (
    SignalInput,
    SentinelOutput,
    ActivityEvent,
    AgentStatus,
    VerificationCheck,
    VerificationOutput,
    VerificationSourceType,
)
from backend.services.llm import generate_structured
from backend.services.budget import check_budget_or_stop, get_budget
from backend.services.events import publish_event
from backend.services.logger import get_logger
from backend.services.tracing import trace_agent
from backend.services.context import (
    get_competitor_profile,
    load_competitor_profile_for_pipeline,
)
from backend.agents.state import PipelineState
from backend.agents.tools.web_search import search_web
from backend.agents.tools.url_scraper import scrape_url

logger = get_logger("verifier")

VERIFIER_DECISION_PROMPT = """You are the Verifier — a skeptical competitive intelligence analyst.

You receive a signal and the results of PRIMARY-SOURCE verification checks.
Your job is to decide if this signal is REAL enough to spend research budget on.

Rules (strict):
- VERIFIED only if at least ONE of: official company source confirms it, signal URL content supports it,
  OR two or more independent credible news/tech publications corroborate the same specific claim.
- UNVERIFIED if: no primary confirmation, only rumor forums / social speculation, or checks contradict the headline.
- Do NOT verify based on vague industry chatter unrelated to this specific event.
- When checks are inconclusive but multiple credible outlets report the same announcement → VERIFIED.
- When checks found nothing matching the headline → UNVERIFIED (likely fabricated or premature leak).

You are a gate against hallucinated signals. When in doubt, REJECT (is_verified=false).

CRITICAL: The primary competitor is given as **Primary entity**. Evidence about a different
company (e.g. a homonym product name) does NOT count. Reject if checks only match the wrong company."""


def _slug_company(name: str) -> str:
    """Best-effort domain slug from company name."""
    slug = re.sub(r"[^a-z0-9]+", "", name.lower())
    return slug or "company"


def _guess_domains(entity: str) -> list[str]:
    slug = _slug_company(entity)
    return [f"{slug}.com", f"www.{slug}.com", f"blog.{slug}.com"]


def _resolve_primary_entity(signal: SignalInput, sentinel: SentinelOutput) -> str:
    """Prefer explicit competitor_name over short product codenames in entities."""
    if signal.competitor_name and signal.competitor_name.strip():
        return signal.competitor_name.strip()
    if sentinel.entities:
        return max(sentinel.entities, key=len).strip()
    return "company"


def _entity_tokens(entity: str) -> list[str]:
    """Significant tokens for matching (e.g. 'Nimbus AI' -> ['nimbus'])."""
    stop = {"inc", "corp", "ltd", "the", "and", "for", "with", "from"}
    tokens = [
        t for t in re.findall(r"[a-z0-9]{3,}", entity.lower())
        if t not in stop
    ]
    return tokens or [entity.lower()]


def _evidence_mentions_entity(entity: str, text: str) -> bool:
    """True if text plausibly refers to the primary competitor, not a homonym."""
    if not entity or not text:
        return False
    lower = text.lower()
    tokens = _entity_tokens(entity)
    return any(tok in lower for tok in tokens)


def _apply_entity_gate(
    checks: list[VerificationCheck],
    primary_entity: str,
) -> list[VerificationCheck]:
    """Downgrade passes that cite the wrong company (e.g. Orion Advisor vs Nimbus AI)."""
    gated: list[VerificationCheck] = []
    for check in checks:
        if not check.passed:
            gated.append(check)
            continue
        blob = f"{check.evidence} {check.url or ''}"
        if _evidence_mentions_entity(primary_entity, blob):
            gated.append(check)
            continue
        gated.append(
            VerificationCheck(
                source_type=check.source_type,
                passed=False,
                url=check.url,
                evidence=(
                    f"Wrong entity (expected '{primary_entity}'): {check.evidence[:200]}"
                ),
            )
        )
    return gated


async def _golden_path_seeded_verification(
    signal: SignalInput,
) -> VerificationOutput | None:
    """
    Demo competitor with seeded DB profile: accept signal for pipeline exercise.

    Avoids false passes on homonyms (Orion Advisor, etc.) when Nimbus AI is fictional.
    """
    if (signal.source or "").lower() != "golden_path":
        return None
    if not signal.competitor_name:
        return None
    profile = await get_competitor_profile(signal.competitor_name)
    if not profile:
        return None
    content = f"{signal.title} {signal.content or ''}"
    if not _evidence_mentions_entity(signal.competitor_name, content):
        return None
    return VerificationOutput(
        is_verified=True,
        reasoning=(
            f"Golden path demo: '{signal.competitor_name}' has seeded institutional memory "
            f"({len(profile.launch_history)} prior launches on record). Accepting signal for "
            "controlled pipeline demonstration."
        ),
        checks=[
            VerificationCheck(
                source_type=VerificationSourceType.SIGNAL_URL,
                passed=True,
                evidence=(
                    f"Seeded competitor profile: {profile.shipping_record[:120]}"
                ),
            ),
        ],
    )


def _demo_verification_bypass(signal: SignalInput) -> bool:
    """Allow golden-path demo signals to pass when APIs are flaky."""
    if not settings.DEMO_MODE:
        return False
    title_lower = signal.title.lower()
    for fragment in settings.VERIFIER_DEMO_PASS_TITLES.split(","):
        if fragment.strip() and fragment.strip().lower() in title_lower:
            return True
    return False


async def _check_signal_url(signal: SignalInput, title: str) -> VerificationCheck:
    if not signal.url:
        return VerificationCheck(
            source_type=VerificationSourceType.SIGNAL_URL,
            passed=False,
            evidence="No signal URL provided",
        )
    content = await scrape_url(signal.url, max_chars=2500)
    if not content or len(content) < 80:
        return VerificationCheck(
            source_type=VerificationSourceType.SIGNAL_URL,
            passed=False,
            url=signal.url,
            evidence="Could not scrape signal URL or content too short",
        )
    title_tokens = [t.lower() for t in re.findall(r"[a-zA-Z]{4,}", title)][:6]
    hits = sum(1 for t in title_tokens if t in content.lower())
    passed = hits >= 1 or len(content) > 400
    return VerificationCheck(
        source_type=VerificationSourceType.SIGNAL_URL,
        passed=passed,
        url=signal.url,
        evidence=content[:400] if passed else "Scraped page does not support headline",
    )


async def _check_official_blog(entity: str, title: str) -> VerificationCheck:
    domains = _guess_domains(entity)
    query = f"{entity} {title[:80]} announcement"
    results = await search_web(
        query,
        max_results=4,
        search_depth="basic",
        include_domains=domains[:3],
    )
    if not results:
        results = await search_web(f"site:{domains[0]} {title[:60]}", max_results=3)
    if results:
        top = results[0]
        blob = f"{top.title} {top.snippet}"
        passed = _evidence_mentions_entity(entity, blob)
        return VerificationCheck(
            source_type=VerificationSourceType.OFFICIAL_BLOG,
            passed=passed,
            url=top.url,
            evidence=(
                f"Official-domain hit: {top.title} — {top.snippet[:200]}"
                if passed
                else f"Official domain result does not mention '{entity}': {top.title[:80]}"
            ),
        )
    return VerificationCheck(
        source_type=VerificationSourceType.OFFICIAL_BLOG,
        passed=False,
        evidence=f"No results on official domains ({', '.join(domains[:2])})",
    )


async def _check_product_page(entity: str, title: str) -> VerificationCheck:
    query = f"{entity} pricing signup product page {title[:40]}"
    results = await search_web(query, max_results=3, search_depth="basic")
    for r in results:
        lower = r.url.lower()
        blob = f"{r.title} {r.snippet}"
        if any(x in lower for x in ("/pricing", "/product", "/signup", "/register", "/demo")):
            if _evidence_mentions_entity(entity, blob):
                return VerificationCheck(
                    source_type=VerificationSourceType.PRODUCT_PAGE,
                    passed=True,
                    url=r.url,
                    evidence=f"Product/pricing surface found: {r.title}",
                )
    if results:
        return VerificationCheck(
            source_type=VerificationSourceType.PRODUCT_PAGE,
            passed=False,
            url=results[0].url,
            evidence="Search found mentions but no clear product/pricing/signup page",
        )
    return VerificationCheck(
        source_type=VerificationSourceType.PRODUCT_PAGE,
        passed=False,
        evidence="No product or pricing page found",
    )


async def _check_linkedin(entity: str, title: str) -> VerificationCheck:
    query = f"site:linkedin.com {entity} {title[:50]}"
    results = await search_web(query, max_results=3)
    if results:
        top = results[0]
        blob = f"{top.title} {top.snippet}"
        passed = _evidence_mentions_entity(entity, blob)
        return VerificationCheck(
            source_type=VerificationSourceType.LINKEDIN,
            passed=passed,
            url=top.url,
            evidence=(
                f"LinkedIn mention: {top.snippet[:200]}"
                if passed
                else f"LinkedIn hit does not mention '{entity}'"
            ),
        )
    return VerificationCheck(
        source_type=VerificationSourceType.LINKEDIN,
        passed=False,
        evidence="No LinkedIn company/posts found for this signal",
    )


async def _check_news_corroboration(entity: str, title: str) -> VerificationCheck:
    query = f"{entity} {title[:100]}"
    results = await search_web(query, max_results=5, search_depth="basic")
    credible = [
        r
        for r in results
        if r.relevance >= 0.35
        and _evidence_mentions_entity(entity, f"{r.title} {r.snippet}")
    ]
    if len(credible) >= 2:
        urls = ", ".join(r.url for r in credible[:3])
        return VerificationCheck(
            source_type=VerificationSourceType.NEWS_CORROBORATION,
            passed=True,
            evidence=f"{len(credible)} independent sources: {urls[:300]}",
        )
    if len(credible) == 1:
        return VerificationCheck(
            source_type=VerificationSourceType.NEWS_CORROBORATION,
            passed=False,
            url=credible[0].url,
            evidence="Only one corroborating source — insufficient for strict verification",
        )
    return VerificationCheck(
        source_type=VerificationSourceType.NEWS_CORROBORATION,
        passed=False,
        evidence="No credible news corroboration",
    )


async def run_verification_checks(
    signal: SignalInput,
    sentinel: SentinelOutput,
) -> list[VerificationCheck]:
    """Execute ordered primary-source checks."""
    entity = _resolve_primary_entity(signal, sentinel)
    title = signal.title

    checks: list[VerificationCheck] = []
    checks.append(await _check_signal_url(signal, title))
    checks.append(await _check_official_blog(entity, title))
    checks.append(await _check_product_page(entity, title))
    checks.append(await _check_linkedin(entity, title))
    if sentinel.event_type.value == "earnings":
        sec_results = await search_web(
            f"site:sec.gov {entity} {title[:40]}",
            max_results=2,
        )
        checks.append(
            VerificationCheck(
                source_type=VerificationSourceType.SEC_FILING,
                passed=bool(sec_results),
                url=sec_results[0].url if sec_results else None,
                evidence=sec_results[0].snippet[:200] if sec_results else "No SEC filing found",
            )
        )
    checks.append(await _check_news_corroboration(entity, title))
    return _apply_entity_gate(checks, entity)


def _rule_based_verified(checks: list[VerificationCheck], primary_entity: str) -> bool:
    """Strict pre-LLM gate: primary pass OR strong news corroboration."""
    primary_types = {
        VerificationSourceType.SIGNAL_URL,
        VerificationSourceType.OFFICIAL_BLOG,
        VerificationSourceType.LINKEDIN,
        VerificationSourceType.SEC_FILING,
    }
    primary_pass = any(
        c.passed
        for c in checks
        if c.source_type in primary_types
        and _evidence_mentions_entity(primary_entity, c.evidence)
    )
    news_pass = any(
        c.passed and c.source_type == VerificationSourceType.NEWS_CORROBORATION
        for c in checks
    )
    return primary_pass or news_pass


@trace_agent("verifier")
async def verifier_node(state: PipelineState) -> dict:
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

    profile = state.get("competitor_profile")
    if profile is None:
        profile = await load_competitor_profile_for_pipeline(signal, sentinel)

    await publish_event("agent_activity", {
        "agent": "verifier",
        "status": "running",
        "message": "Running primary-source verification checks...",
        "workflow_id": workflow_id,
    })

    if _demo_verification_bypass(signal):
        output = VerificationOutput(
            is_verified=True,
            reasoning="Demo mode: golden-path signal auto-verified.",
            checks=[
                VerificationCheck(
                    source_type=VerificationSourceType.SIGNAL_URL,
                    passed=True,
                    evidence="DEMO_MODE bypass",
                )
            ],
        )
        return _verified_return(output, budget, workflow_id, profile)

    primary_entity = _resolve_primary_entity(signal, sentinel)
    golden = await _golden_path_seeded_verification(signal)
    if golden:
        wf_logger.info("verifier_golden_path_seeded", competitor=signal.competitor_name)
        return _verified_return(golden, budget, workflow_id, profile)

    checks: list[VerificationCheck] = []
    degraded = False
    try:
        checks = await run_verification_checks(signal, sentinel)
    except Exception as e:
        wf_logger.error("verifier_checks_failed", error=str(e))
        degraded = True
        checks = [
            VerificationCheck(
                source_type=VerificationSourceType.SIGNAL_URL,
                passed=False,
                evidence=f"Verification tools failed: {str(e)[:120]}",
            )
        ]

    checks_text = "\n".join(
        f"- [{c.source_type.value}] {'PASS' if c.passed else 'FAIL'}: {c.evidence[:250]}"
        for c in checks
    )
    prompt = (
        f"**Signal:** {signal.title}\n"
        f"**Primary entity (must match):** {primary_entity}\n"
        f"**Event type:** {sentinel.event_type}\n"
        f"**Entities:** {', '.join(sentinel.entities)}\n\n"
        f"**Verification checks:**\n{checks_text}\n\n"
        "Decide is_verified and explain reasoning in 2-3 sentences."
    )

    is_verified = False
    reasoning = ""

    try:
        from pydantic import BaseModel, Field

        class VerifierDecision(BaseModel):
            is_verified: bool = Field(description="True only if signal is real enough to investigate")
            reasoning: str

        decision, _usage = await generate_structured(
            prompt=prompt,
            response_model=VerifierDecision,
            system=VERIFIER_DECISION_PROMPT,
            temperature=0.1,
            model="llama-3.3-70b-versatile",
            budget=budget,
            agent="verifier",
        )
        is_verified = decision.is_verified
        reasoning = decision.reasoning
    except Exception as e:
        wf_logger.warning("verifier_llm_failed", error=str(e))
        degraded = True
        is_verified = (
            _rule_based_verified(checks, primary_entity)
            if not settings.VERIFIER_STRICT
            else False
        )
        reasoning = (
            f"LLM decision unavailable; rule-based result={'verified' if is_verified else 'rejected'}. "
            f"Error: {str(e)[:80]}"
        )

    if settings.VERIFIER_STRICT and not degraded:
        rule_ok = _rule_based_verified(checks, primary_entity)
        if not rule_ok:
            is_verified = False
            reasoning = (
                f"{reasoning} [Strict gate: no primary source or strong corroboration.]"
            ).strip()

    if degraded and settings.VERIFIER_STRICT:
        is_verified = False
        reasoning = f"Verification degraded — failing closed. {reasoning}"

    output = VerificationOutput(
        is_verified=is_verified,
        reasoning=reasoning,
        checks=checks,
        degraded=degraded,
    )

    wf_logger.info(
        "verifier_completed",
        is_verified=output.is_verified,
        checks_passed=sum(1 for c in checks if c.passed),
        degraded=degraded,
    )

    if not output.is_verified:
        await publish_event("agent_activity", {
            "agent": "verifier",
            "status": "error",
            "message": "Signal unverified — pipeline halted.",
            "detail": output.reasoning,
            "workflow_id": workflow_id,
        })
        await publish_event("verifier.rejected", {
            "agent": "verifier",
            "status": "rejected",
            "message": "Signal unverified — pipeline halted",
            "detail": output.reasoning,
            "checks_passed": sum(1 for c in output.checks if c.passed),
            "checks_total": len(output.checks),
            "workflow_id": workflow_id,
        })
        return {
            "verification_output": output,
            "competitor_profile": profile,
            "current_agent": "verifier",
            "should_continue": False,
            "error": f"Signal unverified by primary sources: {output.reasoning}",
            **budget.state_updates(),
            "activity_log": [
                ActivityEvent(
                    agent="verifier",
                    status=AgentStatus.ERROR,
                    message="Signal Unverified",
                    detail=output.reasoning,
                    workflow_id=workflow_id,
                )
            ],
        }

    return _verified_return(output, budget, workflow_id, profile)


def _verified_return(output, budget, workflow_id, profile):
    return {
        "verification_output": output,
        "competitor_profile": profile,
        "current_agent": "verifier",
        "should_continue": True,
        **budget.state_updates(),
        "activity_log": [
            ActivityEvent(
                agent="verifier",
                status=AgentStatus.DONE,
                message="Verified from primary sources",
                detail=output.reasoning,
                workflow_id=workflow_id,
            )
        ],
    }
