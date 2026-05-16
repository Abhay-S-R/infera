"""
Phase 4 Dev 4 tests — Sentinel, Scout, Strategist, Scribe agent logic.
Run: pytest tests/test_phase4_dev4_agents.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.schemas import (
    SignalInput,
    SentinelOutput,
    ResearchAgenda,
    ResearchQuestion,
    EventType,
    CompetitorProfile,
    AnalysisOutput,
    CeoQaPair,
    InsightType,
    ReportOutput,
)
from backend.agents.nodes.scout import _generate_agenda, _build_synthesis_prompt
from backend.agents.nodes.scribe import scribe_node
from backend.core.budget import TokenBudget

@pytest.mark.asyncio
async def test_scout_fallback_agenda():
    signal = SignalInput(title="Competitor launched feature X")
    sentinel_output = SentinelOutput(
        relevance_score=0.9,
        should_investigate=True,
        event_type=EventType.PRODUCT_LAUNCH,
        entities=["Acme"],
        summary="Launch",
        reasoning="Important",
    )
    # Force fallback by causing generate_structured to raise exception
    with patch("backend.agents.nodes.scout.generate_structured", side_effect=Exception("API Error")):
        agenda = await _generate_agenda(signal, sentinel_output, None, "General")
        
    assert isinstance(agenda, ResearchAgenda)
    assert len(agenda.questions) >= 2
    assert agenda.questions[0].question == "Competitor launched feature X"

def test_scout_synthesis_prompt_includes_agenda():
    signal = MagicMock()
    sentinel_output = MagicMock()
    agenda = ResearchAgenda(
        questions=[ResearchQuestion(question="What is the pricing?", why_it_matters="Pricing matters", priority=5)]
    )
    prompt = _build_synthesis_prompt(signal, sentinel_output, [], [], agenda=agenda)
    assert "## Research Agenda" in prompt
    assert "What is the pricing?" in prompt

@pytest.mark.asyncio
async def test_scribe_post_processing():
    signal = SignalInput(title="Signal")
    analysis = AnalysisOutput(
        executive_summary="Exec",
        market_impact="Market",
        competitive_positioning="Comp",
        insights=[],
        strategic_recommendations=[],
        ceo_qa_pairs=[
            CeoQaPair(question="Will they beat us?", answer="No.", confidence=InsightType.CONFIRMED),
            CeoQaPair(question="When is GA?", answer="Next Q.", confidence=InsightType.SPECULATIVE),
        ],
        overall_confidence=0.8
    )
    
    # Mock prepare_for_scribe to return our analysis
    mock_ctx = ({}, analysis, [], 100)
    
    with patch("backend.agents.nodes.scribe.prepare_for_scribe", return_value=mock_ctx):
        # Mock generate_structured to return a report that needs formatting
        raw_report = ReportOutput(
            title="Test Report",
            exec_brief="This is [CONFIRMED] true.",
            tech_brief="This is [INFERRED] maybe.",
            sales_brief="This is [SPECULATIVE] likely.",
            risk_brief="Risk.",
            confidence_score=0.8
        )
        with patch("backend.agents.nodes.scribe.generate_structured", return_value=(raw_report, {})):
            # Create pipeline state
            state = {"signal": signal, "budget": TokenBudget(1000)}
            
            result = await scribe_node(state)
            
            assert "report_output" in result
            report = result["report_output"]
            
            # Check confidence marker replacement
            assert "✅ **CONFIRMED:**" in report.exec_brief
            assert "⚠️ *INFERRED:*" in report.tech_brief
            assert "❓ **SPECULATIVE:**" in report.sales_brief
            
            # Check CEO QA pairs appended to exec brief
            assert "## Likely CEO Questions" in report.exec_brief
            assert "Will they beat us?" in report.exec_brief
            assert "✅ **CONFIRMED:** No." in report.exec_brief
            assert "❓ **SPECULATIVE:** Next Q." in report.exec_brief
