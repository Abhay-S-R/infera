import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.services.events import create_redis, get_pubsub_channel

router = APIRouter()


@router.websocket("/ws/activity")
async def activity_feed(websocket: WebSocket) -> None:
    await websocket.accept()
    redis = create_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(get_pubsub_channel())

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
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
        await pubsub.unsubscribe(get_pubsub_channel())
        await pubsub.close()
        await redis.close()
