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
from backend.services.tracing import trace_agent

logger = get_logger("scribe")

SYSTEM_PROMPT = """You are an Executive Report Writer for a top-tier competitive intelligence firm.
Your job is to take structured competitive analysis and research, and weave it into 4 targeted, highly readable, beautifully formatted Markdown documents.

Rules:
1. You must generate 4 distinct documents with STRICT constraints:
   - Executive Brief (for CEO/Leadership): MUST be ≤220 words. Include exactly ONE `## Decision Needed` section. Do not include CEO questions (they will be appended automatically).
   - Technical Brief (for Engineering/Product): ~400-600 words. Focus on architecture, build vs buy, and parity timeline.
   - Sales Brief (for GTM teams): Bulleted battle card and objection handlers.
   - Risk Brief (for Legal/Risk): Markdown table with columns: Segment | Exposure | Why.
2. When mentioning specific insights, you MUST prefix them with their confidence level:
   - ✅ **CONFIRMED:**
   - ⚠️ *INFERRED:*
   - ❓ **SPECULATIVE:**
3. Create a catchy, professional title for the overall report.
"""

@trace_agent("scribe")
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

    # Extract sources from research (now a list from parallel scouts)
    sources = []
    if research:
        for r in research:
            sources.extend([res.url for res in r.results if res.url])

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
{chr(10).join(f"- [{i.type.upper()}] {i.insight} (Impact: {i.impact})" for i in analysis.insights)}

RECOMMENDATIONS:
{chr(10).join(f"- {r}" for r in analysis.strategic_recommendations)}

CEO QA PAIRS:
{chr(10).join(f"- Q: {qa.question} | A: {qa.answer} ({qa.confidence})" for qa in analysis.ceo_qa_pairs)}

Please generate the 4 final targeted briefs based on this intelligence.
"""

    log.info("scribe_generating_report")

    try:
        # Call the LLM
        report, _usage = await generate_structured(
            prompt=prompt,
            response_model=ReportOutput,
            system=SYSTEM_PROMPT,
            temperature=0.4,
            model="gemini-3.1-flash-lite",
            max_output_tokens=8192,
            budget=budget,
            agent="scribe",
        )
        
        # Ensure we attach the sources correctly
        report.sources = sources
        report.generated_at = datetime.now(timezone.utc)
        
        # Post-process: Append CEO Q&A to Executive Brief
        if analysis.ceo_qa_pairs:
            qa_text = "\\n\\n## Likely CEO Questions\\n"
            for qa in analysis.ceo_qa_pairs:
                conf = str(qa.confidence).lower()
                marker = "❓ **SPECULATIVE:** "
                if "confirmed" in conf: marker = "✅ **CONFIRMED:** "
                elif "inferred" in conf: marker = "⚠️ *INFERRED:* "
                qa_text += f"**Q: {qa.question}**\\n{marker}{qa.answer}\\n\\n"
            report.exec_brief += qa_text
            
        # Post-process: simple confidence marker enforcement if the LLM missed it
        def format_report_with_confidence(text: str) -> str:
            text = text.replace("[CONFIRMED]", "✅ **CONFIRMED:**")
            text = text.replace("[INFERRED]", "⚠️ *INFERRED:*")
            text = text.replace("[SPECULATIVE]", "❓ **SPECULATIVE:**")
            return text

        report.exec_brief = format_report_with_confidence(report.exec_brief)
        report.tech_brief = format_report_with_confidence(report.tech_brief)
        report.sales_brief = format_report_with_confidence(report.sales_brief)
        report.risk_brief = format_report_with_confidence(report.risk_brief)
        
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
