"""
Phase 4 Dev 2 foundation tests — schemas, verification rules, profile helpers.
Run without live APIs: pytest tests/test_phase4_dev2_foundation.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.schemas import (
    VerificationCheck,
    VerificationOutput,
    VerificationSourceType,
    CompetitorProfile,
    LaunchHistoryEntry,
    CeoQaPair,
    InsightType,
)
from backend.agents.verifier import (
    _apply_entity_gate,
    _evidence_mentions_entity,
    _resolve_primary_entity,
    _rule_based_verified,
    _slug_company,
)
from backend.services.context import competitor_profile_prompt_block, resolve_competitor_name
from backend.models.schemas import SignalInput, SentinelOutput, EventType


class TestSchemasContract:
    def test_verification_output_shape(self):
        out = VerificationOutput(
            is_verified=False,
            reasoning="No primary sources",
            checks=[
                VerificationCheck(
                    source_type=VerificationSourceType.OFFICIAL_BLOG,
                    passed=False,
                    evidence="none",
                )
            ],
        )
        assert out.is_verified is False
        assert len(out.checks) == 1

    def test_competitor_profile_roundtrip(self):
        p = CompetitorProfile(
            competitor_name="Acme",
            shipping_record="Slow shipper",
            launch_history=[
                LaunchHistoryEntry(product="X", announced="2024", notes="late")
            ],
        )
        data = p.model_dump()
        assert CompetitorProfile.model_validate(data).competitor_name == "Acme"

    def test_ceo_qa_pair_for_dev4(self):
        pair = CeoQaPair(
            question="Will enterprise churn?",
            answer="Low near-term risk in healthcare vertical.",
            confidence=InsightType.INFERRED,
        )
        assert pair.confidence == InsightType.INFERRED


class TestVerifierRules:
    def test_evidence_mentions_entity(self):
        assert _evidence_mentions_entity("Nimbus AI", "Nimbus AI launched Orion")
        assert not _evidence_mentions_entity("Nimbus AI", "Orion Advisor Solutions Denali")

    def test_entity_gate_downgrades_wrong_company(self):
        checks = [
            VerificationCheck(
                source_type=VerificationSourceType.NEWS_CORROBORATION,
                passed=True,
                evidence="Orion Advisor launches Denali AI platform",
            )
        ]
        gated = _apply_entity_gate(checks, "Nimbus AI")
        assert gated[0].passed is False

    def test_resolve_primary_entity_prefers_competitor_name(self):
        signal = SignalInput(title="t", competitor_name="Nimbus AI")
        sentinel = SentinelOutput(
            relevance_score=0.8,
            should_investigate=True,
            event_type=EventType.PRODUCT_LAUNCH,
            entities=["Orion", "Nimbus AI"],
            summary="s",
            reasoning="r",
        )
        assert _resolve_primary_entity(signal, sentinel) == "Nimbus AI"

    def test_rule_based_requires_primary_or_news(self):
        checks = [
            VerificationCheck(
                source_type=VerificationSourceType.OFFICIAL_BLOG,
                passed=True,
                evidence="Acme Corp official blog post confirms launch",
            )
        ]
        assert _rule_based_verified(checks, "Acme Corp") is True

    def test_rule_based_fails_all_fail(self):
        checks = [
            VerificationCheck(
                source_type=VerificationSourceType.OFFICIAL_BLOG,
                passed=False,
                evidence="none",
            ),
            VerificationCheck(
                source_type=VerificationSourceType.NEWS_CORROBORATION,
                passed=False,
                evidence="none",
            ),
        ]
        assert _rule_based_verified(checks, "Acme Corp") is False

    def test_slug_company(self):
        assert _slug_company("Nimbus AI") == "nimbusai"


class TestContextHelpers:
    def test_resolve_competitor_from_signal(self):
        signal = SignalInput(title="Test", competitor_name="Nimbus AI")
        assert resolve_competitor_name(signal) == "Nimbus AI"

    def test_resolve_competitor_from_sentinel_entity(self):
        signal = SignalInput(title="Test")
        sentinel = SentinelOutput(
            relevance_score=0.8,
            should_investigate=True,
            event_type=EventType.PRODUCT_LAUNCH,
            entities=["Nimbus AI"],
            summary="s",
            reasoning="r",
        )
        assert resolve_competitor_name(signal, sentinel) == "Nimbus AI"

    def test_profile_prompt_block_includes_history(self):
        profile = CompetitorProfile(
            competitor_name="Nimbus AI",
            shipping_record="14mo avg slip",
            launch_history=[
                LaunchHistoryEntry(product="Copilot", announced="2023", notes="late")
            ],
            hiring_signals=["40 ML hires"],
        )
        block = competitor_profile_prompt_block(profile)
        assert "INSTITUTIONAL MEMORY" in block
        assert "14mo" in block
        assert "Copilot" in block
