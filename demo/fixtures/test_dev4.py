import asyncio
import json
from backend.models.schemas import SignalInput, ResearchOutput, SearchResult
from backend.agents.state import PipelineState
from backend.agents.strategist import strategist_node
from backend.agents.scribe import scribe_node
from backend.services.logger import configure_logging

async def run_test():
    configure_logging()
    
    print("========================================")
    print("DEV 4 PHASE 1: END-TO-END TEST")
    print("========================================")
    
    signal = SignalInput(
        title="OpenAI announces GPT-5 release date",
        source="news",
        content="OpenAI has officially announced that GPT-5 will be released next month, featuring vastly improved reasoning capabilities and native multi-modal integration. The new model is expected to outperform previous versions significantly and lower API costs by 20%."
    )
    
    mock_research = ResearchOutput(
        queries_used=["GPT-5 release date OpenAI", "GPT-5 specs vs GPT-4", "GPT-5 API cost reduction"],
        results=[
            SearchResult(title="OpenAI's GPT-5: Everything we know", url="https://techcrunch.com/gpt-5", snippet="GPT-5 arrives next month with 20% lower costs..."),
            SearchResult(title="Anthropic prepares Claude 3.5 in response", url="https://theverge.com/claude", snippet="Anthropic is rushing its next release to compete with GPT-5...")
        ],
        key_findings=[
            "GPT-5 will be released next month.",
            "It features vastly improved reasoning and native multi-modal support.",
            "API costs will be reduced by 20%.",
            "Competitors like Anthropic are accelerating their own release timelines in response."
        ],
        sources_consulted=2,
        raw_content_summary="OpenAI is launching GPT-5 next month. It offers better reasoning, native multi-modal features, and a 20% cost reduction. This is putting pressure on competitors like Anthropic who are speeding up their own product roadmaps."
    )
    
    state: PipelineState = {
        "signal": signal,
        "research_output": mock_research,
        "workflow_id": "test-workflow-001",
        "retry_count": 0,
        "max_retries": 3,
        "should_continue": True,
        "current_agent": "strategist",
        "error": None,
        "activity_log": [],
        "total_tokens_used": 0,
        "total_cost_usd": 0.0
    }
    
    print("\n[1] Running Strategist Agent...")
    strat_result = await strategist_node(state)
    
    if "error" in strat_result:
        print(f"Strategist failed: {strat_result['error']}")
        return
        
    analysis = strat_result["analysis_output"]
    print(f"Strategist completed successfully! Confidence: {analysis.overall_confidence}")
    print(f"Executive Summary: {analysis.executive_summary}")
    
    # Update state with Strategist output
    state["analysis_output"] = analysis
    
    print("\n[2] Running Scribe Agent...")
    scribe_result = await scribe_node(state)
    
    if "error" in scribe_result:
        print(f"Scribe failed: {scribe_result['error']}")
        return
        
    report = scribe_result["report_output"]
    print(f"Scribe completed successfully! Report Title: {report.title}")
    print("\n=== FINAL MARKDOWN REPORT ===")
    print(report.full_report_markdown)
    print("=============================")

if __name__ == "__main__":
    asyncio.run(run_test())
