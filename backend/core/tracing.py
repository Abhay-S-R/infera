"""Omium tracing integration for INFERA.

Provides a `get_tracer()` function that returns a tracer initialized with
the Omium API key and endpoint from settings.

Usage:
    tracer = get_tracer()
    with tracer.start_span("agent_name", workflow_id="..."):
        # do work
"""
from __future__ import annotations

from typing import Any, Optional
from backend.core.config import settings
from backend.core.logger import get_logger
import functools
from typing import Callable, Any

logger = get_logger("tracing")

_TRACER_INSTANCE = None


class _NoopSpan:
    """Fallback span when Omium is unavailable."""
    def __init__(self, name: str, **attrs: Any):
        self.name = name
        self.attrs = attrs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set_attribute(self, k: str, v: Any) -> None:
        pass


class _NoopTracer:
    """Fallback tracer when Omium is unavailable."""
    def start_span(self, name: str, **attrs: Any):
        return _NoopSpan(name, **attrs)


def init_omium() -> None:
    """Initialize the Omium client globally.
    
    Called once on FastAPI startup to configure Omium with API credentials.
    Must be called before any spans are created.
    """
    global _TRACER_INSTANCE
    
    if not settings.OMIUM_API_KEY:
        logger.warning("omium_not_configured", reason="OMIUM_API_KEY not set in environment")
        _TRACER_INSTANCE = _NoopTracer()
        return
    
    try:
        import omium  # type: ignore
        
        omium.init(
            api_key=settings.OMIUM_API_KEY,
            endpoint=settings.OMIUM_ENDPOINT,
            workspace=settings.OMIUM_WORKSPACE,
        )
        logger.info("omium_initialized", endpoint=settings.OMIUM_ENDPOINT, workspace=settings.OMIUM_WORKSPACE)
        _TRACER_INSTANCE = _OmiumTracer()
    except ImportError:
        logger.warning("omium_not_installed", reason="omium package not installed")
        _TRACER_INSTANCE = _NoopTracer()
    except Exception as e:
        logger.error("omium_init_failed", error=str(e))
        _TRACER_INSTANCE = _NoopTracer()


class _OmiumTracer:
    """Tracer that delegates to Omium."""
    
    def start_span(self, name: str, **attrs: Any):
        try:
            import omium  # type: ignore
            span = omium.start_span(name, attributes=attrs)
            return span
        except Exception as e:
            logger.debug("omium_span_failed", name=name, error=str(e))
            return _NoopSpan(name, **attrs)


def get_tracer():
    """Return the global Omium tracer instance.
    
    If Omium is not initialized, returns a no-op tracer.
    Call `init_omium()` during app startup to activate real tracing.
    """
    global _TRACER_INSTANCE
    
    if _TRACER_INSTANCE is None:
        logger.debug("tracer_not_initialized", msg="Call init_omium() during startup")
        return _NoopTracer()
    
    return _TRACER_INSTANCE


def trace_agent(name: str) -> Callable:
    """Decorator to automatically trace agent nodes and extract workflow_id/retry."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(state, *args, **kwargs) -> Any:
            tracer = get_tracer()
            workflow_id = state.get("workflow_id", "unknown")
            retry_count = state.get("retry_count", 0)
            with tracer.start_span(name, workflow_id=workflow_id, retry=retry_count):
                return await func(state, *args, **kwargs)
        return wrapper
    return decorator
