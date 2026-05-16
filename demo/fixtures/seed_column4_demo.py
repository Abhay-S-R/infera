#!/usr/bin/env python3
"""
Seed Column 4 demo data — institutional memory for Nimbus AI.

Run before hackathon demo:
  python demo/fixtures/seed_column4_demo.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://ascent:ascent_pass@localhost:5433/ascent_db",
)

from backend.models.schemas import CompetitorProfile, LaunchHistoryEntry
from backend.pipeline.context import upsert_competitor_profile
from backend.core.database import init_db

DEMO_COMPETITOR = "Nimbus AI"


async def main() -> None:
    await init_db()
    profile = CompetitorProfile(
        competitor_name=DEMO_COMPETITOR,
        shipping_record=(
            "Announced 3 major platform launches since 2022; average 14 months from "
            "announcement to GA — pattern of overhyped timelines."
        ),
        launch_history=[
            LaunchHistoryEntry(
                product="Nimbus Analytics Pro",
                announced="2024-03",
                shipped="2025-01",
                notes="Shipped ~10 months late vs initial 'Q2 2024' messaging",
            ),
            LaunchHistoryEntry(
                product="Nimbus Copilot",
                announced="2023-09",
                shipped="2024-08",
                notes="6-month slip; limited enterprise features at launch",
            ),
        ],
        hiring_signals=[
            "40 ML engineers hired Q1 2025 — telegraphed new AI platform bet",
            "VP Product from Snowflake joined March 2025",
        ],
        ceo_public_statements=[
            "SaaStr 2025: 'Enterprise AI orchestration is our defining 2025 investment'",
        ],
        last_assessment=(
            "Historically over-announces AI capabilities; delivery credibility is the key "
            "risk when evaluating new launches."
        ),
    )
    await upsert_competitor_profile(profile)
    print(f"Seeded competitor profile for: {DEMO_COMPETITOR}")
    print(f"  Launch history entries: {len(profile.launch_history)}")
    print(f"  Hiring signals: {len(profile.hiring_signals)}")


if __name__ == "__main__":
    asyncio.run(main())
