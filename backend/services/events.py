import json
from typing import Any

import redis.asyncio as redis

from backend.config import settings


REDIS_CHANNEL = "activity_events"


def create_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_pubsub_channel() -> str:
    return REDIS_CHANNEL


async def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    client = create_redis()
    try:
        await client.publish(REDIS_CHANNEL, json.dumps({"type": event_type, "data": payload}))
    finally:
        await client.close()
