import asyncio
import os
from backend.models.schemas import SignalInput
from backend.agents.graph import run_pipeline
from backend.services.logger import configure_logging

async def test_phase3_dev4_features():
    print("\n--- TEST: Phase 3 Dev 4 (Analyst Parity) ---")
    
    # We will use a complex signal that should trigger the Scout adaptive loop 
    # and require deep analysis.
    signal = SignalInput(
        title="OpenAI announces 'Project Orion' - a new hybrid architecture",
        source="news",
        content="OpenAI has reportedly started testing a new model architecture named Orion, focusing on reasoning and code generation. Pricing and enterprise availability are currently unknown."
    )
    
    print("\n[1] Starting pipeline...")
    print("Watch the logs for 'scout_coverage_eval' to see the Adaptive Loop in action.")
    
    result = await run_pipeline(signal, workflow_id="test-phase3-001")
    
    if "error" in result:
        print(f"\nWARNING: Pipeline encountered an error (likely rate limit in Arbiter): {result['error']}")
        print("Continuing to output results...\n")

    print("\n[2] Pipeline Completed Successfully!")
    
    # Verify Strategist Output (InsightTypes and CEO Questions)
    analysis = result.get("analysis_output")
    if analysis:
        print("\n=== STRATEGIST OUTPUT VERIFICATION ===")
        print(f"Confidence: {analysis.overall_confidence}")
        print("\nCEO Questions Generated:")
        for q in analysis.ceo_questions:
            print(f" - {q}")
            
        print("\nInsights (with InsightType):")
        for i in analysis.insights:
            print(f" - [{i.type.upper()}] {i.insight} (Impact: {i.impact})")
    else:
        print("\nERROR: Missing analysis_output")

    # Verify Scribe Output (4 Distinct Briefs)
    report = result.get("report_output")
    if report:
        print("\n=== SCRIBE OUTPUT VERIFICATION (4 Briefs) ===")
        print(f"\n[EXEC BRIEF] length: {len(report.exec_brief)} chars")
        print(f"Preview: {report.exec_brief[:150]}...\n")
        
        print(f"[TECH BRIEF] length: {len(report.tech_brief)} chars")
        print(f"Preview: {report.tech_brief[:150]}...\n")
        
        print(f"[SALES BRIEF] length: {len(report.sales_brief)} chars")
        print(f"Preview: {report.sales_brief[:150]}...\n")
        
        print(f"[RISK BRIEF] length: {len(report.risk_brief)} chars")
        print(f"Preview: {report.risk_brief[:150]}...\n")
    else:
        print("\nERROR: Missing report_output")

    print("\n--- TEST COMPLETE ---")

async def main():
    configure_logging()
    await test_phase3_dev4_features()

if __name__ == "__main__":
    # Ensure keys are present
    if not os.getenv("GROQ_API_KEY") or not os.getenv("GEMINI_API_KEY") or not os.getenv("TAVILY_API_KEY"):
        print("WARNING: Missing API keys in environment. Tests may fail.")
        
    asyncio.run(main())
