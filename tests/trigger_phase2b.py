import asyncio
import httpx
import sys

API_URL = "http://localhost:8000/webhooks/news"

SCENARIOS = {
    "1_low_relevance": {
        "title": "Local bakery introduces new blueberry muffin recipe",
        "source": "Local News",
        "content": "A local bakery has changed their muffin recipe today.",
        "description": "Gate Test 1: Should score < 0.4 relevance and stop after Sentinel."
    },
    "2_zero_sources": {
        "title": "Google announces acquisition of stealth startup QuantumHyperNetDriveXYZ99 for $2B",
        "source": "Tech Insider",
        "content": "Google just announced they are acquiring a startup called QuantumHyperNetDriveXYZ99. This is a massive move in the quantum space.",
        "description": "Gate Test 2: Sentinel will pass this because it mentions Google and an acquisition, but Scout will find 0 sources for the fake company name. Will skip Strategist and go to Scribe."
    },
    "3_arbiter_retry": {
        "title": "Unverified leak suggests OpenAI is secretly planning to acquire Anthropic for $100 Billion",
        "source": "Tech Rumor Mill",
        "content": "An anonymous insider claims OpenAI and Anthropic are in late-stage merger talks to consolidate the AI industry.",
        "description": "Arbiter Test: Sentinel passes it. Scout finds zero official evidence. Strategist guesses. Arbiter strictly REJECTS because we explicitly updated its prompt to reject unverified rumors → Triggers retry."
    },
    "4_full_approval": {
        "title": "NVIDIA officially announces Blackwell B200 GPU with massive performance leap",
        "source": "Tech News",
        "content": "NVIDIA announced the Blackwell B200 GPU today, promising 30x inference performance compared to Hopper.",
        "description": "Clean Run Test: High quality signal. Scout finds evidence, Strategist analyzes, Arbiter APPROVES on first try."
    }
}

async def trigger_scenario(name: str):
    data = SCENARIOS[name]
    print(f"\n==================================================")
    print(f"Triggering Scenario: {name}")
    print(f"Expected Behavior: {data['description']}")
    print(f"==================================================")
    
    payload = {
        "title": data["title"],
        "source": data["source"],
        "content": data["content"],
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(API_URL, json=payload)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 202:
                print("✅ Webhook accepted!")
                print("👉 Watch your uvicorn terminal or the dashboard to see the agents in action.")
            else:
                print(f"❌ Error: {response.text}")
        except httpx.ConnectError:
            print(f"❌ Failed to connect to {API_URL}. Is uvicorn running?")

async def main():
    if len(sys.argv) > 1:
        scenario = sys.argv[1]
        if scenario in SCENARIOS:
            await trigger_scenario(scenario)
        else:
            print(f"Unknown scenario '{scenario}'. Available:")
            for k in SCENARIOS:
                print(f"  {k}")
    else:
        print("ASCENT Phase 2b Manual Testing Script")
        print("Run with a scenario name to trigger the pipeline:")
        for k, v in SCENARIOS.items():
            print(f"\n  python3 tests/trigger_phase2b.py {k}")
            print(f"    -> {v['description']}")

if __name__ == "__main__":
    asyncio.run(main())
