import asyncio
from backend.agents.graph import run_pipeline
from backend.models.schemas import SignalInput

async def main():
    signal = SignalInput(
        title="NVIDIA officially announces Blackwell B200 GPU with massive performance leap",
        source="Tech News",
        content="NVIDIA announced the Blackwell B200 GPU today, promising 30x inference performance compared to Hopper."
    )
    result = await run_pipeline(signal=signal)
    print("Done!")
    for e in result.get("activity_log", []):
        print(f"[{e.agent}] {e.status}: {e.message}")

if __name__ == "__main__":
    asyncio.run(main())
