"""
ASCENT Structured Logger — JSON-formatted logging with agent context.

Every agent and service should use this module for logging:

    from backend.services.logger import get_logger
    logger = get_logger("sentinel")

    logger.info("signal_scored", relevance=0.85, entity="NVIDIA")
    logger.error("llm_failed", error="timeout", attempt=3)

Output (one JSON object per line):
    {"ts":"2026-05-15T14:30:00.123Z","level":"INFO","logger":"sentinel","event":"signal_scored","relevance":0.85,"entity":"NVIDIA"}

Why JSON logging?
  - Machine-parseable → easy to search with jq, pipe to monitoring
  - Structured fields → filter by agent, workflow_id, error type
  - No need for regex-based log parsing
"""
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
        }

        # The 'event' is the primary log message (structured logging convention)
        log_entry["event"] = record.getMessage()

        # Merge any extra structured fields passed via logger.info("event", extra={...})
        # or via our custom LoggerAdapter
        if hasattr(record, "_structured_data"):
            log_entry.update(record._structured_data)

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class StructuredLogger:
    """
    A wrapper around Python's logger that supports structured key-value logging.

    Usage:
        logger = get_logger("agent_name")
        logger.info("event_name", key1="val1", key2=42)
        logger.error("something_broke", error=str(e), workflow_id="abc123")
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        """Internal log method that injects structured data."""
        if not self._logger.isEnabledFor(level):
            return

        record = self._logger.makeRecord(
            name=self._logger.name,
            level=level,
            fn="",
            lno=0,
            msg=event,
            args=(),
            exc_info=None,
        )
        record._structured_data = kwargs  # type: ignore[attr-defined]
        self._logger.handle(record)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, event, **kwargs)

    def with_context(self, **ctx: Any) -> "BoundLogger":
        """
        Create a child logger with persistent context fields.

        Useful for binding workflow_id or agent name once:
            wf_logger = logger.with_context(workflow_id="abc123")
            wf_logger.info("step_started")  # workflow_id auto-included
        """
        return BoundLogger(self, ctx)


class BoundLogger:
    """Logger with pre-bound context fields that get included in every log entry."""

    def __init__(self, parent: StructuredLogger, context: dict[str, Any]):
        self._parent = parent
        self._context = context

    def _merge(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        merged = {**self._context, **kwargs}
        return merged

    def debug(self, event: str, **kwargs: Any) -> None:
        self._parent.debug(event, **self._merge(kwargs))

    def info(self, event: str, **kwargs: Any) -> None:
        self._parent.info(event, **self._merge(kwargs))

    def warning(self, event: str, **kwargs: Any) -> None:
        self._parent.warning(event, **self._merge(kwargs))

    def error(self, event: str, **kwargs: Any) -> None:
        self._parent.error(event, **self._merge(kwargs))

    def critical(self, event: str, **kwargs: Any) -> None:
        self._parent.critical(event, **self._merge(kwargs))

    def with_context(self, **ctx: Any) -> "BoundLogger":
        """Chain additional context on top of existing context."""
        return BoundLogger(self._parent, {**self._context, **ctx})


# ─── Module-level setup ───

_initialized = False


def _setup_root_logger() -> None:
    """Configure the root logger with JSON output. Called once."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    from backend.config import settings

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Remove any default handlers
    root.handlers.clear()

    # JSON handler → stderr
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    # Quiet noisy libraries
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio", "google"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def configure_logging() -> None:
    """Public entry point to initialize logging. Called by main.py on startup."""
    _setup_root_logger()


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger for the given module/agent name.

    Args:
        name: Logger name, e.g. "sentinel", "scout", "llm", "api".

    Returns:
        StructuredLogger instance with JSON output.
    """
    _setup_root_logger()
    return StructuredLogger(f"ascent.{name}")
