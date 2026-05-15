"""
ASCENT Phase 1 — End-to-End Verification Test Suite

Run from project root:
    python tests/test_phase1_e2e.py

Tests all Phase 1 deliverables:
  1. LLM plain text (Groq)
  2. LLM plain text (Gemini)
  3. LLM structured output (Groq → SentinelOutput)
  4. LLM structured output (Gemini → AnalysisOutput)
  5. Web search (Tavily)
  6. URL scraper
  7. Full pipeline (Sentinel→Scout→Strategist→Arbiter→Scribe)
  8. API health check
  9. Webhook → Background pipeline → Report in DB
"""
import asyncio
import sys
import os
import time
import json
import traceback

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ─── Helpers ───

PASS = "\033[92m✅ PASS\033[0m"
FAIL = "\033[91m❌ FAIL\033[0m"
SKIP = "\033[93m⏭️  SKIP\033[0m"
results = []


def log(test_name, passed, detail="", elapsed=0):
    status = PASS if passed else FAIL
    results.append((test_name, passed))
    time_str = f" ({elapsed:.1f}s)" if elapsed else ""
    print(f"  {status}  {test_name}{time_str}")
    if detail:
        for line in detail.split("\n")[:8]:
            print(f"         {line}")
    print()


async def timed(coro):
    start = time.monotonic()
    result = await coro
    return result, time.monotonic() - start


# ─── Test 1: Groq plain text ───

async def test_groq_plain_text():
    from backend.services.llm import generate

    (text, _usage), elapsed = await timed(
        generate("Say hello in one sentence.", system="You are helpful.", model="llama-3.3-70b-versatile")
    )
    ok = len(text) > 0 and elapsed < 10
    log("Groq plain text generation", ok, f"Response: {text[:80]}", elapsed)
    return ok


# ─── Test 2: Gemini plain text ───

async def test_gemini_plain_text():
    from backend.services.llm import generate

    (text, _usage), elapsed = await timed(
        generate("Say hello in one sentence.", system="You are helpful.", model="gemini-3.1-flash-lite")
    )
    ok = len(text) > 0 and elapsed < 15
    log("Gemini plain text generation", ok, f"Response: {text[:80]}", elapsed)
    return ok


# ─── Test 3: Groq structured output (SentinelOutput) ───

async def test_groq_structured():
    from backend.services.llm import generate_structured
    from backend.models.schemas import SentinelOutput

    (result, _usage), elapsed = await timed(
        generate_structured(
            prompt="Classify: NVIDIA launches H200 GPU with 2x performance.",
            response_model=SentinelOutput,
            system="Classify this competitive signal.",
            model="llama-3.3-70b-versatile",
        )
    )
    ok = (
        isinstance(result, SentinelOutput)
        and 0 <= result.relevance_score <= 1
        and len(result.entities) > 0
        and len(result.summary) > 10
    )
    log(
        "Groq structured output (SentinelOutput)", ok,
        f"Relevance: {result.relevance_score}, Entities: {result.entities[:3]}",
        elapsed,
    )
    return ok


# ─── Test 4: Gemini structured output (AnalysisOutput) ───

async def test_gemini_structured():
    from backend.services.llm import generate_structured
    from backend.models.schemas import AnalysisOutput

    (result, _usage), elapsed = await timed(
        generate_structured(
            prompt="Analyze: NVIDIA launched H200 with 2x perf. Key finding: Competitor AMD has no response yet.",
            response_model=AnalysisOutput,
            system="Produce competitive analysis.",
            model="gemini-3.1-flash-lite",
            max_output_tokens=8192,
        )
    )
    ok = (
        isinstance(result, AnalysisOutput)
        and len(result.executive_summary) > 20
        and 0 <= result.overall_confidence <= 1
    )
    log(
        "Gemini structured output (AnalysisOutput)", ok,
        f"Confidence: {result.overall_confidence}, Summary: {result.executive_summary[:80]}",
        elapsed,
    )
    return ok


# ─── Test 5: Web search (Tavily) ───

async def test_web_search():
    from backend.agents.tools.web_search import search_web

    results_list, elapsed = await timed(
        search_web("NVIDIA GPU announcement 2026", max_results=3)
    )
    ok = len(results_list) > 0 and all(r.url for r in results_list)
    detail = "\n".join(f"[{r.relevance:.2f}] {r.title[:60]}" for r in results_list[:3])
    log("Tavily web search", ok, detail, elapsed)
    return ok


# ─── Test 6: URL scraper ───

async def test_url_scraper():
    from backend.agents.tools.url_scraper import scrape_url

    content, elapsed = await timed(
        scrape_url("https://example.com", max_chars=1000)
    )
    ok = content is not None and len(content) > 20
    log("URL scraper (example.com)", ok, f"Scraped {len(content)} chars", elapsed)
    return ok


# ─── Test 7: Full pipeline end-to-end ───

async def test_full_pipeline():
    from backend.agents.graph import run_pipeline
    from backend.models.schemas import SignalInput

    signal = SignalInput(
        title="Google announces Gemini 3.0 with autonomous agent capabilities",
        source="TechCrunch",
    )

    start = time.monotonic()
    result = await run_pipeline(signal)
    elapsed = time.monotonic() - start

    # Check all agent outputs exist
    sentinel = result.get("sentinel_output")
    research = result.get("research_output")
    analysis = result.get("analysis_output")
    report = result.get("report_output")
    events = result.get("activity_log", [])

    checks = {
        "sentinel_exists": sentinel is not None,
        "sentinel_relevant": sentinel and sentinel.relevance_score > 0.3,
        "research_exists": research is not None,
        "research_has_findings": research and len(research.key_findings) > 0,
        "research_has_sources": research and research.sources_consulted > 0,
        "analysis_exists": analysis is not None,
        "report_exists": report is not None,
        "report_has_title": report and len(report.title) > 10,
        "report_has_markdown": report and len(report.full_report_markdown) > 100,
        "events_logged": len(events) >= 4,
    }

    all_ok = all(checks.values())
    failed = [k for k, v in checks.items() if not v]

    detail_lines = [
        f"Sentinel: relevance={sentinel.relevance_score if sentinel else 'N/A'}, entities={sentinel.entities[:3] if sentinel else []}",
        f"Scout: {research.sources_consulted if research else 0} sources, {len(research.key_findings) if research else 0} findings",
        f"Report: {report.title[:60] if report else 'N/A'}",
        f"Confidence: {report.confidence_score if report else 'N/A'}",
        f"Activity events: {len(events)}",
    ]
    if failed:
        detail_lines.append(f"FAILED checks: {failed}")

    log("Full pipeline (Sentinel→Scout→Strategist→Scribe)", all_ok, "\n".join(detail_lines), elapsed)
    return all_ok


# ─── Test 8: API health check ───

async def test_api_health():
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8000/health", timeout=5)
            ok = resp.status_code == 200
            log("API health check (GET /health)", ok, f"Status: {resp.status_code}, Body: {resp.text[:80]}")
            return ok
    except Exception as e:
        log("API health check (GET /health)", False, f"Server not reachable: {e}")
        return False


# ─── Test 9: Webhook → Pipeline → Report ───

async def test_webhook_to_report():
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            # Send webhook
            resp = await client.post(
                "http://localhost:8000/webhooks/news",
                json={"title": "Phase1 E2E Test: Amazon launches new cloud AI service", "source": "Reuters"},
                timeout=5,
            )
            webhook_ok = resp.status_code in (200, 202) and "webhook_id" in resp.json()
            webhook_id = resp.json().get("webhook_id", "?")

            if not webhook_ok:
                log("Webhook → Report (HTTP flow)", False, f"Webhook failed: {resp.status_code}")
                return False

            # Wait for pipeline to complete (up to 90 seconds)
            print(f"         Webhook accepted (id={webhook_id}). Waiting up to 90s for pipeline...")
            for i in range(18):  # 18 * 5 = 90 seconds
                await asyncio.sleep(5)
                reports_resp = await client.get("http://localhost:8000/api/reports", timeout=5)
                reports = reports_resp.json()
                # Check if our report appeared (look for the title)
                matching = [r for r in reports if "Amazon" in r.get("title", "") and "Phase1" not in r.get("title", "")]
                if matching or any("Amazon" in r.get("title", "") for r in reports):
                    matching = [r for r in reports if "Amazon" in r.get("title", "")]
                    if matching:
                        report = matching[0]
                        is_real = "Stub" not in report.get("full_report_markdown", "Stub")
                        has_sources = len(report.get("sources", [])) > 0
                        ok = is_real and has_sources
                        log(
                            "Webhook → Report (HTTP flow)", ok,
                            f"Title: {report['title'][:60]}\nConfidence: {report.get('confidence_score')}\nSources: {len(report.get('sources', []))}",
                        )
                        return ok
                sys.stdout.write(f"\r         Waiting... {(i+1)*5}s")
                sys.stdout.flush()

            print()
            log("Webhook → Report (HTTP flow)", False, "Report did not appear within 90 seconds")
            return False

    except Exception as e:
        log("Webhook → Report (HTTP flow)", False, f"Error: {e}")
        return False


# ─── Main Runner ───

async def main():
    print()
    print("=" * 60)
    print("  ASCENT Phase 1 — End-to-End Verification")
    print("=" * 60)
    print()

    # Unit-level tests (fast)
    tests = [
        ("── LLM Service Tests ──", [
            ("Groq plain text generation", test_groq_plain_text),
            ("Gemini plain text generation", test_gemini_plain_text),
            ("Groq structured output", test_groq_structured),
            ("Gemini structured output", test_gemini_structured),
        ]),
        ("── Tool Tests ──", [
            ("Tavily web search", test_web_search),
            ("URL scraper", test_url_scraper),
        ]),
        ("── Pipeline Test ──", [
            ("Full pipeline", test_full_pipeline),
        ]),
        ("── API Tests (requires uvicorn running on :8000) ──", [
            ("API health", test_api_health),
            ("Webhook → Report", test_webhook_to_report),
        ]),
    ]

    for section_name, section_tests in tests:
        print(section_name)
        for test_name, test_fn in section_tests:
            try:
                await test_fn()
            except Exception:
                log(test_name, False, traceback.format_exc())

    # Summary
    print()
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    color = "\033[92m" if passed == total else "\033[91m"
    print(f"  {color}RESULTS: {passed}/{total} tests passed\033[0m")
    print("=" * 60)

    if passed < total:
        print("\n  Failed tests:")
        for name, ok in results:
            if not ok:
                print(f"    ❌ {name}")
        print()
        sys.exit(1)
    else:
        print("\n  🎉 Phase 1 is fully operational!\n")


if __name__ == "__main__":
    asyncio.run(main())
