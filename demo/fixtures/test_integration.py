import asyncio
from backend.models.schemas import SignalInput
from backend.agents.graph import run_pipeline
from backend.core.logger import configure_logging

async def run_integration_test():
    configure_logging()
    
    print("========================================")
    print("PHASE 1 INTEGRATION TEST (Dev 2 + Dev 4)")
    print("========================================")
    
    # We provide only the raw signal. 
    # Sentinel will filter it, Scout will research it, 
    # Strategist will analyze it, and Scribe will write the report.
    signal = SignalInput(
        title="OpenAI announces GPT-5 release date",
        source="news",
        content="OpenAI has officially announced that GPT-5 will be released next month, featuring vastly improved reasoning capabilities and native multi-modal integration. The new model is expected to outperform previous versions significantly and lower API costs by 20%."
    )
    
    print("[+] Starting the full ASCENT pipeline...")
    final_state = await run_pipeline(signal, workflow_id="integration-test-001")
    
    print("\n========================================")
    print("PIPELINE EXECUTION COMPLETE")
    print("========================================")
    
    if "error" in final_state and final_state["error"]:
        print(f"Pipeline failed with error: {final_state['error']}")
        return
        
    print("\n[Activity Log]:")
    for event in final_state.get("activity_log", []):
        print(f" - [{event.agent}] {event.status}: {event.message} ({event.detail or ''})")
        
    if "report_output" in final_state and final_state["report_output"]:
        report = final_state["report_output"]
        print(f"\n[Final Output] Report Title: {report.title}")
        print(f"Confidence Score: {report.confidence_score}")
        print("\n=== FULL MARKDOWN REPORT ===\n")
        print(report.full_report_markdown)
        print("\n============================")
    else:
        print("\nPipeline did not produce a report (might have been filtered by Sentinel).")

if __name__ == "__main__":
    asyncio.run(run_integration_test())
