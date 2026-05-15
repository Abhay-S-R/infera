#!/usr/bin/env python3
"""
Golden path demo runner — Phase 4 Column 4.

Uses seeded fictional competitor "Nimbus AI" (run seed_column4_demo.py first).
Verifier accepts via institutional seed; Scouts/Strategist use profile context.

Usage:
  .venv/bin/python demo/fixtures/seed_column4_demo.py
  .venv/bin/python demo/fixtures/golden_path.py
  .venv/bin/python demo/fixtures/golden_path.py --run-number 2
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://ascent:ascent_pass@localhost:5433/ascent_db",
)

from backend.agents.graph import run_pipeline
from backend.models.schemas import SignalInput
from backend.services.context import get_competitor_profile
from backend.services.logger import configure_logging
from backend.services.profile_writer import update_competitor_profile_from_run


# No placeholder URL — avoids bogus 404 + wrong-entity web noise.
# source=golden_path triggers profile-backed verification in verifier.py.
DEMO_SIGNAL = SignalInput(
    title="Nimbus AI announces Orion enterprise analytics platform with AI orchestration",
    source="golden_path",
    content=(
        "Nimbus AI unveiled Orion, an enterprise analytics platform with AI orchestration. "
        "Pricing and general availability have not been announced. "
        "This follows Nimbus AI's pattern of pre-announcing ahead of GA."
    ),
    competitor_name="Nimbus AI",
)


async def run_golden_path(run_number: int = 1) -> int:
    configure_logging()
    workflow_id = f"golden-path-{run_number:03d}"

    print(f"\n{'=' * 60}")
    print(f"  GOLDEN PATH — Run #{run_number}  (workflow_id={workflow_id})")
    print(f"{'=' * 60}\n")

    profile_before = await get_competitor_profile("Nimbus AI")
    launches_before = len(profile_before.launch_history) if profile_before else 0
    assessment_before = (profile_before.last_assessment[:80] if profile_before else "none")

    if profile_before:
        print(f"Profile BEFORE: {launches_before} launches, assessment={assessment_before}...")
    else:
        print("Profile BEFORE: none — run: python demo/fixtures/seed_column4_demo.py")
        return 1

    print("\nStarting pipeline...\n")
    result = await run_pipeline(DEMO_SIGNAL, workflow_id=workflow_id)

    verification = result.get("verification_output")
    scouts = result.get("research_output", [])
    analysis = result.get("analysis_output")
    report = result.get("report_output")
    sentinel = result.get("sentinel_output")
    err = result.get("error")

    # Profile write-back (same as API dispatcher — was missing for CLI runs)
    if analysis:
        updated = await update_competitor_profile_from_run(
            signal=DEMO_SIGNAL,
            sentinel=sentinel,
            analysis=analysis,
            research_list=scouts,
        )
        if updated:
            print(f"\nProfile write-back: OK ({len(updated.launch_history)} launches in DB)")

    print("\n--- RESULTS ---")
    if verification:
        passed = sum(1 for c in verification.checks if c.passed)
        print(f"Verifier: verified={verification.is_verified} ({passed}/{len(verification.checks)} checks)")
        print(f"  reasoning: {verification.reasoning[:160]}...")
        for c in verification.checks:
            mark = "PASS" if c.passed else "FAIL"
            print(f"  [{mark}] {c.source_type.value}: {c.evidence[:90]}")
    else:
        print("Verifier: (no output)")

    print(f"Scouts: {len(scouts)} result(s)")
    if analysis:
        print(f"Strategist: confidence={analysis.overall_confidence:.2f}, "
              f"insights={len(analysis.insights)}, ceo_qa_pairs={len(analysis.ceo_qa_pairs)}")
    if report:
        print(f"Scribe: title={report.title[:70]}...")
        print(f"  exec={len(report.exec_brief)} tech={len(report.tech_brief)} "
              f"sales={len(report.sales_brief)} risk={len(report.risk_brief)} chars")
    if err:
        print(f"Error: {err[:300]}")

    profile_after = await get_competitor_profile("Nimbus AI")
    launches_after = len(profile_after.launch_history) if profile_after else 0
    if profile_after:
        print(f"\nProfile AFTER: {launches_after} launches (was {launches_before})")
        print(f"  assessment: {profile_after.last_assessment[:120]}...")

    if verification and not verification.is_verified:
        print("\n❌ FAILED: Verifier rejected golden path signal")
        return 1
    if not report:
        print("\n⚠️  No report (pipeline may have halted or budget exceeded)")
        return 1 if err else 0

    if launches_after < launches_before and run_number > 1:
        print("\n⚠️  Profile launch count did not grow — write-back may need richer analysis")

    print("\n✅ Golden path completed")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-number", type=int, default=1)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run_golden_path(args.run_number)))


if __name__ == "__main__":
    main()
