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


class InsightType(str, Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    SPECULATIVE = "speculative"


class VerificationSourceType(str, Enum):
    """Primary-source check types run by the Verifier (Phase 4)."""
    SIGNAL_URL = "signal_url"
    OFFICIAL_BLOG = "official_blog"
    PRODUCT_PAGE = "product_page"
    LINKEDIN = "linkedin"
    SEC_FILING = "sec_filing"
    NEWS_CORROBORATION = "news_corroboration"


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
    investigation_angles: list[str] = Field(default_factory=list, description="3 distinct angles to research (e.g. Financial, Technical, Market)")
    summary: str = Field(description="One-paragraph summary of the signal")
    reasoning: str = Field(description="Why this score was assigned")
    resolved_competitor: Optional[str] = Field(
        default=None,
        description="Canonical competitor name for profile lookup (Dev 4 may set)",
    )


# ─── Phase 4: Primary verification (Dev 2) ───


class VerificationCheck(BaseModel):
    """Result of a single primary-source verification step."""
    source_type: VerificationSourceType
    passed: bool
    url: Optional[str] = None
    evidence: str = Field(default="", description="What was found or why check failed")


class VerificationOutput(BaseModel):
    """Verifier agent output — skeptical gate before Scout fan-out."""
    is_verified: bool
    reasoning: str
    checks: list[VerificationCheck] = Field(default_factory=list)
    degraded: bool = Field(
        default=False,
        description="True if tools failed; pipeline should not auto-pass unverified signals",
    )


# ─── Phase 4: Institutional competitor memory (Dev 2) ───


class LaunchHistoryEntry(BaseModel):
    product: str
    announced: str = ""
    shipped: str = ""
    notes: str = ""


class CompetitorProfile(BaseModel):
    """Structured institutional memory — upserted after each successful run."""
    competitor_name: str
    shipping_record: str = ""
    launch_history: list[LaunchHistoryEntry] = Field(default_factory=list)
    hiring_signals: list[str] = Field(default_factory=list)
    ceo_public_statements: list[str] = Field(default_factory=list)
    last_assessment: str = ""
    updated_at: Optional[datetime] = None


# ─── Phase 4: Scout research agenda (Dev 4 implements generation) ───


class ResearchQuestion(BaseModel):
    question: str
    why_it_matters: str
    priority: int = Field(ge=1, le=5, default=3)


class ResearchAgenda(BaseModel):
    questions: list[ResearchQuestion] = Field(default_factory=list)


# ─── Phase 4: CEO meeting prep (Dev 4 implements generation) ───


class CeoQaPair(BaseModel):
    question: str
    answer: str
    confidence: InsightType = InsightType.INFERRED


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
    agenda: Optional[ResearchAgenda] = Field(
        default=None,
        description="Analyst research agenda (Dev 4: populate before searches)",
    )


class CoverageEvaluation(BaseModel):
    """Evaluation of whether the current research covers the strategic agenda."""
    missing_questions: list[str] = Field(description="Questions not fully answered by current findings")
    confidence: float = Field(ge=0, le=1, description="Confidence that we have enough information")


# ─── Strategist Output ───

class CompetitiveInsight(BaseModel):
    """A single competitive insight with evidence."""
    insight: str
    impact: str = Field(description="High/Medium/Low")
    type: InsightType = Field(description="Categorization of insight validity")
    evidence: list[str] = Field(description="Supporting evidence from research")
    confidence: float = Field(ge=0, le=1)


class AnalysisOutput(BaseModel):
    """Strategist agent's competitive analysis."""
    executive_summary: str = Field(description="2-3 sentence executive summary")
    market_impact: str = Field(description="Analysis of market implications")
    competitive_positioning: str = Field(description="How this affects competitive landscape")
    insights: list[CompetitiveInsight] = Field(default_factory=list)
    strategic_recommendations: list[str] = Field(description="Actionable recommendations")
    ceo_questions: list[str] = Field(
        default_factory=list,
        description="Deprecated — use ceo_qa_pairs; kept for backward compatibility",
    )
    ceo_qa_pairs: list[CeoQaPair] = Field(
        default_factory=list,
        description="Anticipated CEO questions with pre-written answers (Dev 4)",
    )
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
    exec_brief: str = Field(description="Markdown document tailored for the CEO/Executive team")
    tech_brief: str = Field(description="Markdown document tailored for Engineering/Product teams")
    sales_brief: str = Field(description="Markdown document tailored for Sales/GTM teams")
    risk_brief: str = Field(description="Markdown document tailored for Legal/Risk teams")
    confidence_score: float = Field(ge=0, le=1)
    sources: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ReportListItem(BaseModel):
    """Report summary for list endpoints."""
    id: int
    title: str
    competitor: Optional[str] = None
    confidence: float = 0.0
    created_at: datetime


class ReportDetailResponse(BaseModel):
    """Full report with audience-specific documents."""
    id: int
    title: str
    competitor: Optional[str] = None
    confidence: float = 0.0
    created_at: datetime
    executive_summary: str = ""
    full_report_markdown: str = ""
    documents: dict[str, str] = Field(
        default_factory=dict,
        description='Keys: exec, tech, sales, risk',
    )
    sources: list[str] = Field(default_factory=list)


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


# ─── Health / cost stats (Dev 4 Phase 2b) ───

class HealthStatsResponse(BaseModel):
    """Dashboard health panel aggregates."""
    active_workflows: int
    total_reports: int
    total_tokens: int
    estimated_cost: str = Field(description='Formatted USD, e.g. "$12.34"')
    last_workflow_id: Optional[int] = None
    last_workflow_status: Optional[str] = None
    last_workflow_tokens: Optional[int] = None
    last_workflow_error: Optional[str] = None


# ─── Competitors (scheduled scans) ───

class CompetitorCreate(BaseModel):
    name: str
    industry: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    active: bool = True


class CompetitorResponse(BaseModel):
    id: int
    name: str
    industry: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    active: bool = True
    created_at: datetime


class CompetitorProfileResponse(BaseModel):
    """Institutional memory for a competitor (Phase 4)."""
    competitor_name: str
    shipping_record: str = ""
    launch_history: list[LaunchHistoryEntry] = Field(default_factory=list)
    hiring_signals: list[str] = Field(default_factory=list)
    ceo_public_statements: list[str] = Field(default_factory=list)
    last_assessment: str = ""
    updated_at: Optional[datetime] = None
    found: bool = True
