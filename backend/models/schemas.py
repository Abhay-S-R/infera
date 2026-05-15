"""
ASCENT Schemas — Pydantic models for structured data flowing between agents.
ALL agents must use these schemas. No raw dicts or untyped strings between agents.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# ─── Enums ───

class EventType(str, Enum):
    PRODUCT_LAUNCH = "product_launch"
    FUNDING = "funding"
    ACQUISITION = "acquisition"
    PARTNERSHIP = "partnership"
    LEADERSHIP = "leadership_change"
    EARNINGS = "earnings"
    REGULATION = "regulation"
    GENERAL = "general"


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    SKIPPED = "skipped"


# ─── Webhook / Input ───

class SignalInput(BaseModel):
    """Raw signal from webhook or manual trigger."""
    title: str
    source: str = "manual"
    url: Optional[str] = None
    content: Optional[str] = None
    published_at: Optional[datetime] = None
    competitor_name: Optional[str] = None
    custom_question: Optional[str] = None


# ─── Sentinel Output ───

class SentinelOutput(BaseModel):
    """Sentinel agent's filtering and classification result."""
    relevance_score: float = Field(ge=0, le=1, description="0-1 relevance score")
    should_investigate: bool = Field(description="Whether to proceed with research")
    event_type: EventType = Field(description="Classification of the signal")
    entities: list[str] = Field(default_factory=list, description="Companies/products/people mentioned")
    summary: str = Field(description="One-paragraph summary of the signal")
    reasoning: str = Field(description="Why this score was assigned")


# ─── Scout Output ───

class SearchResult(BaseModel):
    """A single web search result."""
    title: str
    url: str
    snippet: str
    relevance: float = Field(ge=0, le=1, default=0.5)


class ResearchOutput(BaseModel):
    """Scout agent's research findings."""
    queries_used: list[str] = Field(description="Search queries that were executed")
    results: list[SearchResult] = Field(default_factory=list)
    key_findings: list[str] = Field(description="Top 5-10 key findings from research")
    sources_consulted: int = Field(default=0)
    raw_content_summary: str = Field(description="Synthesized summary of all gathered content")


# ─── Strategist Output ───

class CompetitiveInsight(BaseModel):
    """A single competitive insight with evidence."""
    insight: str
    impact: str = Field(description="High/Medium/Low")
    evidence: list[str] = Field(description="Supporting evidence from research")
    confidence: float = Field(ge=0, le=1)


class AnalysisOutput(BaseModel):
    """Strategist agent's competitive analysis."""
    executive_summary: str = Field(description="2-3 sentence executive summary")
    market_impact: str = Field(description="Analysis of market implications")
    competitive_positioning: str = Field(description="How this affects competitive landscape")
    insights: list[CompetitiveInsight] = Field(default_factory=list)
    strategic_recommendations: list[str] = Field(description="Actionable recommendations")
    overall_confidence: float = Field(ge=0, le=1, description="Overall confidence in analysis")


# ─── Arbiter Output ───

class ClaimVerification(BaseModel):
    """Verification of a single claim from the analysis."""
    claim: str
    supported: bool
    evidence_for: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ValidationResult(BaseModel):
    """Arbiter agent's validation of the analysis."""
    is_approved: bool = Field(description="Whether analysis passes quality gate")
    overall_confidence: float = Field(ge=0, le=1)
    claim_verifications: list[ClaimVerification] = Field(default_factory=list)
    issues_found: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    retry_with_queries: Optional[list[str]] = Field(default=None, description="If rejected, suggest new search queries")


# ─── Scribe Output ───

class ReportOutput(BaseModel):
    """Scribe agent's final report."""
    title: str
    executive_summary: str
    full_report_markdown: str = Field(description="Complete report in markdown format")
    confidence_score: float = Field(ge=0, le=1)
    sources: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Activity Events (for WebSocket feed) ───

class ActivityEvent(BaseModel):
    """Real-time activity event streamed to the dashboard."""
    agent: str
    status: AgentStatus
    message: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    workflow_id: Optional[str] = None
    tokens_used: Optional[int] = None
