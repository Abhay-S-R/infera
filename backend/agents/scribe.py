"""
ASCENT Scribe Agent — Generates final formatted intelligence reports.
Dev 4 owns this file.
"""
from backend.services.logger import get_logger
from backend.services.llm import generate_structured
from backend.services.budget import check_budget_or_stop, get_budget
from backend.services.context import summarize_for_next_agent
from backend.agents.state import PipelineState
from backend.models.schemas import ReportOutput, ActivityEvent, AgentStatus
from datetime import datetime, timezone

logger = get_logger("scribe")

SYSTEM_PROMPT = """You are an Executive Report Writer for a top-tier competitive intelligence firm.
Your job is to take structured competitive analysis and research, and weave it into a highly readable, beautifully formatted Markdown report.

Rules:
1. The report must be highly professional, structured with clear headings, bullet points, and bold text for emphasis.
2. Ensure you include an Executive Summary, Detailed Insights, Market Impact, and Strategic Recommendations sections.
3. Incorporate source citations smoothly where appropriate.
4. Your output MUST be valid markdown inside the `full_report_markdown` field.
5. Create a catchy, professional title.
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
    ctx_state = await summarize_for_next_agent(state, "scribe", budget=budget)
    analysis = ctx_state.get("analysis_output") or state.get("analysis_output")
    research = ctx_state.get("research_output") or state.get("research_output")

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
