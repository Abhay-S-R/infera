#!/usr/bin/env python3
"""
Phase 4 Dev 2 — test all foundation changes.

Usage (from repo root):
  .venv/bin/python scripts/test_phase4_dev2.py              # offline + DB (no LLM/Tavily)
  .venv/bin/python scripts/test_phase4_dev2.py --live      # + live pipeline (uses APIs $$)
  .venv/bin/python scripts/test_phase4_dev2.py --live-only # skip pytest, only live checks

Requires for offline+DB:
  docker compose up -d
  .venv/bin/python demo/fixtures/seed_column4_demo.py   # optional, script can seed too

Requires for --live:
  GROQ_API_KEY, GEMINI_API_KEY, TAVILY_API_KEY in .env
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Default DB port from docker-compose (host 5433)
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://ascent:ascent_pass@localhost:5433/ascent_db",
    ),
)

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "


def header(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def run_pytest() -> bool:
    header("1. Unit tests (no APIs)")
    venv_py = ROOT / ".venv" / "bin" / "python"
    py = str(venv_py) if venv_py.is_file() else sys.executable
    r = subprocess.run(
        [py, "-m", "pytest", "tests/test_phase4_dev2_foundation.py", "-v", "--tb=short"],
        cwd=ROOT,
    )
    return r.returncode == 0


async def test_db_profile_roundtrip() -> bool:
    header("2. Database — competitor profile seed & read")
    try:
        from backend.models.database import check_database_connection, init_db
        from backend.services.context import get_competitor_profile, upsert_competitor_profile
        from backend.models.schemas import CompetitorProfile, LaunchHistoryEntry

        if not await check_database_connection():
            print(f"{FAIL} Postgres not reachable. Run: docker compose up -d")
            print(f"    DATABASE_URL={os.environ.get('DATABASE_URL')}")
            return False

        await init_db()
        print(f"{PASS} DB connected, schema initialized")

        demo = CompetitorProfile(
            competitor_name="Nimbus AI Test",
            shipping_record="Test seed: avg 12mo slip",
            launch_history=[
                LaunchHistoryEntry(
                    product="Test Product",
                    announced="2024-01",
                    shipped="2024-12",
                    notes="integration test entry",
                )
            ],
            hiring_signals=["test hire signal"],
            last_assessment="Automated test profile",
        )
        await upsert_competitor_profile(demo)
        loaded = await get_competitor_profile("Nimbus AI Test")
        if not loaded or loaded.shipping_record != demo.shipping_record:
            print(f"{FAIL} Profile roundtrip failed")
            return False
        print(f"{PASS} upsert + get_competitor_profile OK")
        print(f"     shipping_record: {loaded.shipping_record[:60]}...")
        print(f"     launch_history: {len(loaded.launch_history)} entries")
        return True
    except Exception as e:
        print(f"{FAIL} DB test error: {e}")
        return False


def test_pdf_export() -> bool:
    header("3. PDF export (no APIs)")
    try:
        from backend.services.pdf_generator import write_report_pdf
        from backend.models.schemas import ReportOutput

        report = ReportOutput(
            title="Phase 4 Dev 2 Test Report",
            exec_brief="## Decision Needed\nProceed with competitive response.",
            tech_brief="Architecture: likely hybrid cloud inference stack.",
            sales_brief="- Objection: they launched first\n- Response: our SSO is stronger",
            risk_brief="| Segment | Exposure | Why |\n|---------|----------|-----|\n| Fintech | High | overlap |",
            confidence_score=0.72,
        )
        path = write_report_pdf(report, workflow_id="test-dev2-001")
        if not path or not Path(path).is_file():
            print(f"{FAIL} PDF not written")
            return False
        size = Path(path).stat().st_size
        print(f"{PASS} PDF written: {path} ({size} bytes)")
        return True
    except Exception as e:
        print(f"{FAIL} PDF test error: {e}")
        return False


async def test_verifier_checks_offline() -> bool:
    header("4. Verifier rules (offline)")
    from backend.agents.verifier import _rule_based_verified, _slug_company
    from backend.models.schemas import VerificationCheck, VerificationSourceType

    assert _slug_company("Nimbus AI") == "nimbusai"
    primary = [
        VerificationCheck(
            source_type=VerificationSourceType.OFFICIAL_BLOG,
            passed=True,
            evidence="ok",
        )
    ]
    none = [
        VerificationCheck(
            source_type=VerificationSourceType.OFFICIAL_BLOG,
            passed=False,
            evidence="x",
        )
    ]
    if not _rule_based_verified(primary) or _rule_based_verified(none):
        print(f"{FAIL} Rule-based verification logic broken")
        return False
    print(f"{PASS} Verifier rule helpers OK")
    return True


async def seed_demo_profile() -> bool:
    header("5. Seed Nimbus AI demo profile")
    try:
        from demo.fixtures.seed_column4_demo import main as seed_main

        await seed_main()
        from backend.services.context import get_competitor_profile

        p = await get_competitor_profile("Nimbus AI")
        if not p or not p.launch_history:
            print(f"{FAIL} Nimbus AI profile missing after seed")
            return False
        print(f"{PASS} Nimbus AI seeded — {len(p.launch_history)} launches in memory")
        return True
    except Exception as e:
        print(f"{FAIL} Seed failed: {e}")
        return False


def _check_api_keys() -> bool:
    from backend.config import settings

    missing = []
    if not settings.GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not settings.GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not settings.TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")
    if missing:
        print(f"{FAIL} Missing in .env: {', '.join(missing)}")
        return False
    return True


async def test_live_fake_rumor_halt() -> bool:
    header("6. LIVE — fake rumor should halt at Verifier")
    from backend.agents.graph import run_pipeline
    from backend.models.schemas import SignalInput

    signal = SignalInput(
        title="BREAKING: OpenAI acquires Anthropic for $500B effective immediately",
        source="test",
        content="Unverified rumor with no credible backing — integration test.",
        competitor_name="Anthropic",
    )
    print("   Running pipeline (may take 1-3 min)...")
    result = await run_pipeline(signal, workflow_id="test-phase4-fake-rumor")
    verification = result.get("verification_output")
    report = result.get("report_output")
    err = result.get("error") or ""

    if report:
        print(f"{WARN} Expected no report, but Scribe produced one (verifier may have passed)")
    if verification and not verification.is_verified:
        print(f"{PASS} Verifier rejected signal")
        print(f"     reasoning: {verification.reasoning[:200]}")
        print(f"     checks passed: {sum(1 for c in verification.checks if c.passed)}/{len(verification.checks)}")
        return True
    if "unverified" in err.lower() or not result.get("should_continue", True):
        print(f"{PASS} Pipeline halted: {err[:200]}")
        return True
    print(f"{FAIL} Fake rumor was NOT halted — review verifier strictness")
    if verification:
        print(f"     is_verified={verification.is_verified}")
    return False


async def test_live_nimbus_pipeline() -> bool:
    header("7. LIVE — Nimbus AI pipeline (uses seeded memory)")
    from backend.agents.graph import run_pipeline
    from backend.models.schemas import SignalInput
    from backend.services.context import get_competitor_profile

    profile_before = await get_competitor_profile("Nimbus AI")
    if profile_before:
        print(f"   Profile before run: {len(profile_before.launch_history)} launches in DB")

    signal = SignalInput(
        title="Nimbus AI announces Orion analytics platform with enterprise AI features",
        source="test",
        content="Nimbus AI launched Orion, an analytics platform. Pricing unknown.",
        competitor_name="Nimbus AI",
    )
    print("   Running full pipeline (may take 5-15 min)...")
    result = await run_pipeline(signal, workflow_id="test-phase4-nimbus-live")

    verification = result.get("verification_output")
    scouts = result.get("research_output", [])
    analysis = result.get("analysis_output")
    report = result.get("report_output")
    err = result.get("error")

    ok = True
    if verification:
        print(f"   Verifier: verified={verification.is_verified}, checks_passed="
              f"{sum(1 for c in verification.checks if c.passed)}/{len(verification.checks)}")
    else:
        print(f"{WARN} No verification_output in state")
        ok = False

    print(f"   Scouts: {len(scouts)} angle(s)")
    if analysis:
        print(f"   Strategist: confidence={analysis.overall_confidence:.2f}, "
              f"insights={len(analysis.insights)}, ceo_qa_pairs={len(analysis.ceo_qa_pairs)}")
    else:
        print(f"{WARN} No analysis (halted early or scout failure)")
        if err:
            print(f"   error: {err[:300]}")
        ok = False

    if report:
        print(f"   Scribe: exec={len(report.exec_brief)} tech={len(report.tech_brief)} "
              f"sales={len(report.sales_brief)} risk={len(report.risk_brief)} chars")
        from backend.services.pdf_generator import write_report_pdf
        pdf = write_report_pdf(report, "test-phase4-nimbus-live")
        if pdf:
            print(f"   PDF: {pdf}")
    else:
        print(f"{WARN} No report_output")
        ok = False

    profile_after = await get_competitor_profile("Nimbus AI")
    if profile_after:
        print(f"   Profile after run: assessment={profile_after.last_assessment[:80]}...")
    else:
        print(f"{WARN} Profile not found after run (write-back may need completed analysis)")

    if ok and report:
        print(f"{PASS} Full pipeline completed")
        return True
    print(f"{WARN} Pipeline finished with gaps — check logs above")
    return ok


async def main() -> int:
    parser = argparse.ArgumentParser(description="Test Phase 4 Dev 2 changes")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live API tests (Tavily + LLM — costs money/time)",
    )
    parser.add_argument(
        "--live-only",
        action="store_true",
        help="Skip offline tests, only run live pipeline checks",
    )
    args = parser.parse_args()

    print("ASCENT Phase 4 — Dev 2 Foundation Test Suite")
    print(f"Repo: {ROOT}")

    results: list[tuple[str, bool]] = []

    if not args.live_only:
        results.append(("pytest", run_pytest()))
        results.append(("verifier rules", await test_verifier_checks_offline()))
        results.append(("pdf export", test_pdf_export()))
        results.append(("db profile", await test_db_profile_roundtrip()))
        results.append(("seed nimbus", await seed_demo_profile()))

    if args.live or args.live_only:
        if not _check_api_keys():
            return 1
        results.append(("live fake rumor", await test_live_fake_rumor_halt()))
        results.append(("live nimbus pipeline", await test_live_nimbus_pipeline()))

    header("SUMMARY")
    failed = 0
    for name, ok in results:
        icon = PASS if ok else FAIL
        print(f"  {icon} {name}")
        if not ok:
            failed += 1

    if failed:
        print(f"\n{failed} check(s) failed.")
        return 1
    print(f"\n{PASS} All checks passed.")
    if not args.live and not args.live_only:
        print(f"\n{WARN} Run with --live to test Verifier + full pipeline (uses APIs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
