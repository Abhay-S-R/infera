"""
LangGraph PostgreSQL checkpointer lifecycle.

Persists pipeline state after each agent so workflows can resume after a crash.
Uses AsyncPostgresSaver for compatibility with graph.ainvoke().
"""
from __future__ import annotations

import sys
from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from backend.config import settings
from backend.services.logger import get_logger

logger = get_logger("checkpointer")

_cm: Optional[object] = None
_saver: Optional[AsyncPostgresSaver] = None


def _ensure_selector_event_loop() -> None:
    """psycopg async requires SelectorEventLoop on Windows."""
    if sys.platform == "win32":
        import asyncio

        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsSelectorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
async def init_checkpointer() -> AsyncPostgresSaver:
    """Create checkpointer tables and return the shared AsyncPostgresSaver instance."""
    global _cm, _saver
    if _saver is not None:
        return _saver

    _ensure_selector_event_loop()
    _cm = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL_SYNC)
    _saver = await _cm.__aenter__()
    await _saver.setup()
    logger.info("checkpointer_ready")
    return _saver


async def get_checkpointer() -> AsyncPostgresSaver:
    if _saver is None:
        raise RuntimeError("Checkpointer not initialized — call await init_checkpointer() on startup")
    return _saver


async def shutdown_checkpointer() -> None:
    global _cm, _saver
    if _cm is not None:
        await _cm.__aexit__(None, None, None)
        _cm = None
        _saver = None
        logger.info("checkpointer_shutdown")
