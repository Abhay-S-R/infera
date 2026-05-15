"""
ASCENT Strategist Agent — Synthesizes research into competitive analysis.
Dev 4 owns this file.
"""
from backend.services.logger import get_logger
from backend.services.llm import generate_structured
from backend.agents.state import PipelineState
from backend.models.schemas import AnalysisOutput, ActivityEvent, AgentStatus

logger = get_logger("strategist")

SYSTEM_PROMPT = """You are a Principal Competitive Intelligence Analyst.
Your job is to analyze raw web research gathered about a competitive signal and produce a highly structured, objective, and insightful competitive analysis.
You must focus on market impact, competitive positioning, and actionable strategic recommendations.

Rules:
1. Base your analysis STRICTLY on the provided research.
2. Be concise and professional.
3. Assign a confidence score (0.0 to 1.0) based on the quality and volume of the research evidence.
4. Ensure all claims have supporting evidence from the research.
"""

async def strategist_node(state: PipelineState) -> dict:
    """
    Analysis agent — synthesizes research into competitive analysis.
    """
    signal = state.get("signal")
    research = state.get("research_output")
    workflow_id = state.get("workflow_id", "unknown")

    # Bind workflow_id to logger
    log = logger.with_context(workflow_id=workflow_id)
    log.info("strategist_started", signal_title=signal.title)

    # If there's no research output, we can't do much
    if not research or not research.key_findings:
        log.warning("strategist_no_research", reason="Research output is empty or missing")
        return {
            "analysis_output": AnalysisOutput(
                executive_summary="No research was provided to analyze.",
                market_impact="Unknown",
                competitive_positioning="Unknown",
                insights=[],
                strategic_recommendations=[],
                overall_confidence=0.0
            ),
            "current_agent": "strategist",
            "activity_log": [ActivityEvent(
                agent="strategist",
                status=AgentStatus.DONE,
                message="Analysis skipped due to missing research.",
                workflow_id=workflow_id
            )]
        }

    # Construct the user prompt
    prompt = f"""
SIGNAL (What happened):
Title: {signal.title}
Source: {signal.source}
Content/Context: {signal.content or 'None'}

RESEARCH FINDINGS (Evidence gathered):
Key Findings:
{chr(10).join(f"- {f}" for f in research.key_findings)}

Raw Content Summary:
{research.raw_content_summary}

Based on the above, produce a complete competitive analysis.
"""

    log.info("strategist_generating_analysis", queries_used=len(research.queries_used))
    
    try:
        # Call the LLM
        analysis: AnalysisOutput = await generate_structured(
            prompt=prompt,
            response_model=AnalysisOutput,
            system=SYSTEM_PROMPT,
            temperature=0.3  # Low temp for analytical consistency
        )
        
        log.info("strategist_completed", confidence=analysis.overall_confidence)
        
        return {
            "analysis_output": analysis,
            "current_agent": "strategist",
            "activity_log": [ActivityEvent(
                agent="strategist",
                status=AgentStatus.DONE,
                message="Analysis complete",
                detail=f"Generated {len(analysis.insights)} insights. Confidence: {analysis.overall_confidence:.2f}",
                workflow_id=workflow_id
            )]
        }
        
    except Exception as e:
        log.error("strategist_failed", error=str(e))
        return {
            "error": str(e),
            "current_agent": "strategist",
            "activity_log": [ActivityEvent(
                agent="strategist",
                status=AgentStatus.ERROR,
                message=f"Analysis failed: {str(e)}",
                workflow_id=workflow_id
            )]
        }
