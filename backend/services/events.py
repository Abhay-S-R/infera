import json
from typing import Any

import redis.asyncio as redis
from redis.exceptions import RedisError

from backend.config import settings
from backend.services.logger import get_logger

logger = get_logger("events")

REDIS_CHANNEL = "activity_events"


def create_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_pubsub_channel() -> str:
    return REDIS_CHANNEL


async def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    """
    Publish a real-time activity event to Redis.

    If Redis is unavailable, log and return — never crash the pipeline.
    """
    client = create_redis()
    try:
        await client.publish(REDIS_CHANNEL, json.dumps({"type": event_type, "data": payload}))
    except (RedisError, ConnectionError, OSError) as exc:
        logger.warning(
            "redis_publish_failed",
            event_type=event_type,
            error=str(exc)[:200],
        )
    except Exception as exc:
        logger.warning(
            "redis_publish_unexpected",
            event_type=event_type,
            error=str(exc)[:200],
        )
    finally:
        try:
            await client.close()
        except Exception:
            pass
