import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.agents.graph import run_pipeline
from backend.models.schemas import SignalInput

async def main():
    signal = SignalInput(
        title='NVIDIA officially announces Blackwell B200 GPU with massive performance leap',
        source='Tech News',
        content='NVIDIA announced the Blackwell B200 GPU today, promising 30x inference performance compared to Hopper.'
    )
    print('🚀 Starting full pipeline...', flush=True)
    try:
        # Run the pipeline
        result = await run_pipeline(signal=signal)
        
        print('\n=== RESULTS ===')
        
        # 1. Sentinel
        s = result.get('sentinel_output')
        print(f'Sentinel: score={s.relevance_score}, angles={s.investigation_angles}' if s else 'Sentinel: FAIL')
        
        # 2. Scouts
        rl = result.get('research_output', [])
        print(f'Scouts: {len(rl)} parallel results')
        for i, scout_res in enumerate(rl, 1):
            print(f'  - Scout {i}: {scout_res.sources_consulted} sources, {len(scout_res.key_findings)} findings')
        
        # 3. Strategist
        a = result.get('analysis_output')
        if a:
            print(f'Strategist: confidence={a.overall_confidence}, ceo_questions={len(a.ceo_questions)}')
        else:
            print('Strategist: FAIL')
            
        # 4. Arbiter
        v = result.get('validation_result')
        if v:
            print(f'Arbiter: approved={v.is_approved}, confidence={v.overall_confidence}')
        else:
            print('Arbiter: FAIL')
            
        # 5. Scribe (Dev 4's 4-doc outputs)
        r = result.get('report_output')
        if r:
            print(f'Scribe:')
            print(f'  title="{r.title[:80]}"')
            print(f'  exec_brief:  {len(r.exec_brief)} chars')
            print(f'  tech_brief:  {len(r.tech_brief)} chars')
            print(f'  sales_brief: {len(r.sales_brief)} chars')
            print(f'  risk_brief:  {len(r.risk_brief)} chars')
        else:
            print('Scribe: FAIL')
            
        # Check for errors
        if result.get('error'):
            print(f'\n⚠️ Pipeline Error: {result.get("error")}')
        elif r:
            print(f'\n✅ FULL PIPELINE SUCCESS')
            
    except Exception as e:
        print(f'\n❌ PIPELINE FAILED WITH EXCEPTION: {e}')
        
if __name__ == "__main__":
    asyncio.run(main())
