import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.exceptions import RedisError

from backend.core.events import create_redis, get_pubsub_channel
from backend.core.logger import get_logger

router = APIRouter()
logger = get_logger("websocket")


@router.websocket("/ws/activity")
async def activity_feed(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        redis = create_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(get_pubsub_channel())
    except (RedisError, ConnectionError, OSError) as exc:
        logger.warning("websocket_redis_unavailable", error=str(exc)[:200])
        try:
            await websocket.send_json({
                "type": "error",
                "payload": {"message": "Activity feed unavailable (Redis down)"},
            })
        except Exception:
            pass
        await websocket.close(code=1013)
        return

    try:
        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            except (RedisError, ConnectionError, OSError) as exc:
                logger.warning("websocket_redis_read_failed", error=str(exc)[:200])
                break

            if message and message["type"] == "message":
                payload = message["data"]
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                try:
                    payload = json.loads(payload)
                except ValueError:
                    pass
                await websocket.send_json({"type": "activity", "payload": payload})
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await pubsub.unsubscribe(get_pubsub_channel())
            await pubsub.aclose()
            await redis.aclose()
        except Exception:
            pass
