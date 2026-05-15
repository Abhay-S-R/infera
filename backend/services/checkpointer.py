"""
LangGraph PostgreSQL checkpointer lifecycle.

Persists pipeline state after each agent so workflows can resume after a crash.
"""
from __future__ import annotations

from typing import Optional

from langgraph.checkpoint.postgres import PostgresSaver

from backend.config import settings
from backend.services.logger import get_logger

logger = get_logger("checkpointer")

_cm: Optional[object] = None
_saver: Optional[PostgresSaver] = None


def init_checkpointer() -> PostgresSaver:
    """Create checkpointer tables and return the shared PostgresSaver instance."""
    global _cm, _saver
    if _saver is not None:
        return _saver

    _cm = PostgresSaver.from_conn_string(settings.DATABASE_URL_SYNC)
    _saver = _cm.__enter__()
    _saver.setup()
    logger.info("checkpointer_ready")
    return _saver


def get_checkpointer() -> PostgresSaver:
    if _saver is None:
        return init_checkpointer()
    return _saver


def shutdown_checkpointer() -> None:
    global _cm, _saver
    if _cm is not None:
        _cm.__exit__(None, None, None)
        _cm = None
        _saver = None
        logger.info("checkpointer_shutdown")
