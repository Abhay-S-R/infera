import httpx
import asyncio
import json
from datetime import datetime, timezone

# Target endpoint (change localhost to your ngrok/cloudflare tunnel URL if testing remotely)
# Example: URL = "https://your-tunnel-url.ngrok.io/webhooks/news"
URL = "http://localhost:8000/webhooks/news"

async def test_webhook():
    """
    Simulates what Make.com will POST when a new RSS item is found.
    This payload strictly matches the SignalInput schema.
    """
    # Make.com should send a JSON body matching this structure:
    payload = {
        "title": "Anthropic Announces Claude 3.5 Sonnet",
        "source": "RSS - TechCrunch",
        "url": "https://techcrunch.com/2024/06/20/anthropic-claude-3-5-sonnet",
        "content": "Anthropic today announced Claude 3.5 Sonnet, its fastest and most capable model yet...",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "competitor_name": "Anthropic",
        "custom_question": "How does this compare to GPT-4o in terms of pricing and speed?"
    }

    print(f"Sending POST request to {URL}")
    print("Payload:")
    print(json.dumps(payload, indent=2))

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(URL, json=payload, timeout=10.0)
            print(f"\nStatus Code: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error connecting to server: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook())
