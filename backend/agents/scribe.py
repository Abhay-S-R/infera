"""
ASCENT Scribe Agent — Generates final formatted intelligence reports.
Dev 4 owns this file.
"""
from backend.services.logger import get_logger
from backend.services.llm import generate_structured
from backend.services.budget import check_budget_or_stop, get_budget
from backend.services.context import prepare_for_scribe
from backend.agents.state import PipelineState
from backend.models.schemas import ReportOutput, ActivityEvent, AgentStatus
from datetime import datetime, timezone

logger = get_logger("scribe")

SYSTEM_PROMPT = """You are an Executive Report Writer for a top-tier competitive intelligence firm.
Your job is to take structured competitive analysis and research, and produce FOUR audience-specific Markdown briefs plus one combined report.

Rules:
1. **exec_markdown** — CEO brief: 3–5 bullets, strategic implications, decision asks. No jargon.
2. **tech_markdown** — Engineering brief: architecture/product impact, integration risks, build vs buy, technical citations.
3. **sales_markdown** — GTM brief: competitive positioning, talk tracks, objection handling, deal impact.
4. **risk_markdown** — Risk/compliance brief: regulatory exposure, reputational risk, mitigation steps, confidence caveats.
5. **full_report_markdown** — Combined polished report with Executive Summary, Detailed Insights, Market Impact, Strategic Recommendations.
6. Each field must be valid, self-contained markdown with clear headings.
7. **executive_summary** — 2–3 sentence plain-text summary for email subject previews.
8. Create a catchy, professional **title**.
"""

async def scribe_node(state: PipelineState) -> dict:
    """
    Report agent — generates the final deliverable.
    """
    signal = state.get("signal")
    workflow_id = state.get("workflow_id", "unknown")

    log = logger.with_context(workflow_id=workflow_id)
    log.info("scribe_started", signal_title=signal.title if signal else "Unknown")

    stopped = check_budget_or_stop(state, "scribe", workflow_id)
    if stopped:
        stopped["budget_exceeded"] = True
        return stopped

    budget = get_budget(state)
    ctx_state, analysis, research, estimated_tokens = await prepare_for_scribe(state, budget)
    log.info("scribe_context_ready", estimated_state_tokens=estimated_tokens)

    # Guard against missing data
    if not analysis:
        log.error("scribe_failed", reason="Missing analysis_output")
        return {
            "error": "Cannot generate report without analysis_output.",
            "current_agent": "scribe",
            "activity_log": [ActivityEvent(
                agent="scribe",
                status=AgentStatus.ERROR,
                message="Report generation failed: No analysis provided.",
                workflow_id=workflow_id
            )]
        }

    # Extract sources from research
    sources = []
    if research and research.results:
        sources = [res.url for res in research.results if res.url]

    # Construct the user prompt
    prompt = f"""
SIGNAL:
Title: {signal.title if signal else 'Unknown'}
Context: {signal.content if signal and signal.content else 'None'}

ANALYSIS:
Executive Summary: {analysis.executive_summary}
Market Impact: {analysis.market_impact}
Competitive Positioning: {analysis.competitive_positioning}

INSIGHTS:
{chr(10).join(f"- {i.insight} (Impact: {i.impact})" for i in analysis.insights)}

RECOMMENDATIONS:
{chr(10).join(f"- {r}" for r in analysis.strategic_recommendations)}

Please generate the final structured report.
"""

    log.info("scribe_generating_report")

    try:
        # Call the LLM
        report, _usage = await generate_structured(
            prompt=prompt,
            response_model=ReportOutput,
            system=SYSTEM_PROMPT,
            temperature=0.4,
            model="llama-3.3-70b-versatile",
            max_output_tokens=8192,
            budget=budget,
            agent="scribe",
        )
        
        # Ensure we attach the sources correctly
        report.sources = sources
        report.generated_at = datetime.now(timezone.utc)
        if not report.full_report_markdown and report.exec_markdown:
            report.full_report_markdown = report.exec_markdown
        
        log.info("scribe_completed", title=report.title)
        
        return {
            "report_output": report,
            "current_agent": "scribe",
            **budget.state_updates(),
            "activity_log": [ActivityEvent(
                agent="scribe",
                status=AgentStatus.DONE,
                message="Report generated",
                detail=f"Title: {report.title}",
                workflow_id=workflow_id
            )]
        }
        
    except Exception as e:
        log.error("scribe_failed", error=str(e))
        return {
            "error": str(e),
            "current_agent": "scribe",
            "activity_log": [ActivityEvent(
                agent="scribe",
                status=AgentStatus.ERROR,
                message=f"Report generation failed: {str(e)}",
                workflow_id=workflow_id
            )]
        }
