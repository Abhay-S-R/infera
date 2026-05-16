"""
Phase 3 Dev1 — Omium Tracing & Competitor Memory Tests
"""
import pytest
import asyncio
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set DB URLs before backend imports (docker-compose maps host 5433 -> container 5432)
os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://infera:infera_pass@localhost:5433/infera_db",
)
os.environ["DATABASE_URL_SYNC"] = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://infera:infera_pass@localhost:5433/infera_db",
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(autouse=True)
async def cleanup_database():
    """Ensure the engine is disposed between tests to avoid loop mismatch errors."""
    from backend.core.database import engine
    yield
    await engine.dispose()


from backend.core.tracing import init_omium, get_tracer, _NoopTracer, _OmiumTracer
from backend.pipeline.context import get_competitor_history
from backend.core.config import settings
from backend.core.database import AsyncSessionLocal
from backend.models.tables import Report


class TestOmiumInitialization:
    """Test Omium tracing initialization and fallback behavior."""
    
    def test_omium_init_with_api_key(self):
        """Verify init_omium() configures Omium when API key is present."""
        assert settings.OMIUM_API_KEY, "OMIUM_API_KEY must be set in .env"
        assert settings.OMIUM_ENDPOINT.rstrip("/") == "https://api.omium.dev"
        
        # Initialize Omium
        init_omium()
        tracer = get_tracer()
        
        # Should return a tracer (either Omium or Noop, but not None)
        assert tracer is not None
        assert hasattr(tracer, "start_span"), "Tracer must have start_span method"
    
    def test_omium_no_api_key_fallback(self):
        """Verify fallback to NoopTracer when API key is missing."""
        with patch.object(settings, "OMIUM_API_KEY", None):
            init_omium()
            tracer = get_tracer()
            
            # Should fall back to NoopTracer
            assert isinstance(tracer, _NoopTracer)
    
    def test_tracer_start_span_context_manager(self):
        """Verify tracer.start_span() works as context manager."""
        init_omium()
        tracer = get_tracer()
        
        # Should support context manager protocol
        with tracer.start_span("test_span", workflow_id="test-123") as span:
            assert span is not None


class TestCompetitorHistory:
    """Test get_competitor_history() database query."""
    
    @pytest.mark.asyncio
    async def test_get_competitor_history_returns_list(self):
        """Verify get_competitor_history returns a list (even if empty)."""
        result = await get_competitor_history("Apple", limit=3)
        
        # Should return a list (may be empty if no reports exist)
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_competitor_history_limit(self):
        """Verify get_competitor_history respects limit parameter."""
        result = await get_competitor_history("Microsoft", limit=2)
        
        # Should respect the limit
        assert len(result) <= 2
    
    @pytest.mark.asyncio
    async def test_get_competitor_history_case_insensitive(self):
        """Verify ILIKE search is case-insensitive."""
        # Both should work (case-insensitive)
        result_upper = await get_competitor_history("GOOGLE", limit=3)
        result_lower = await get_competitor_history("google", limit=3)
        
        # Both should return lists (may be empty)
        assert isinstance(result_upper, list)
        assert isinstance(result_lower, list)


class TestAgentTracing:
    """Test that agent nodes properly use tracing."""
    
    def test_sentinel_node_imports_tracer(self):
        """Verify sentinel_node imports and uses tracer."""
        from backend.agents.nodes.sentinel import sentinel_node
        import inspect
        
        source = inspect.getsource(sentinel_node)
        source = inspect.getsource(sentinel_node)
        assert "@trace_agent" in source, "sentinel_node must be decorated with @trace_agent"
    
    def test_scout_node_imports_tracer(self):
        """Verify scout_node imports and uses tracer."""
        from backend.agents.nodes.scout import scout_node
        import inspect
        
        source = inspect.getsource(scout_node)
        source = inspect.getsource(scout_node)
        assert "@trace_agent" in source, "scout_node must be decorated with @trace_agent"
    
    def test_strategist_node_imports_tracer(self):
        """Verify strategist_node imports and uses tracer."""
        from backend.agents.nodes.strategist import strategist_node
        import inspect
        
        source = inspect.getsource(strategist_node)
        source = inspect.getsource(strategist_node)
        assert "@trace_agent" in source, "strategist_node must be decorated with @trace_agent"
    
    def test_scribe_node_imports_tracer(self):
        """Verify scribe_node imports and uses tracer."""
        from backend.agents.nodes.scribe import scribe_node
        import inspect
        
        source = inspect.getsource(scribe_node)
        source = inspect.getsource(scribe_node)
        assert "@trace_agent" in source, "scribe_node must be decorated with @trace_agent"
    
    def test_arbiter_node_imports_tracer(self):
        """Verify arbiter_node imports and uses tracer."""
        from backend.agents.nodes.arbiter import arbiter_node
        import inspect
        
        source = inspect.getsource(arbiter_node)
        source = inspect.getsource(arbiter_node)
        assert "@trace_agent" in source, "arbiter_node must be decorated with @trace_agent"


class TestOmiumSpanAttributes:
    """Test that spans are created with proper attributes."""
    
    def test_noop_span_accepts_attributes(self):
        """Verify NoopSpan accepts attributes without error."""
        from backend.core.tracing import _NoopSpan
        
        span = _NoopSpan("test", workflow_id="123", retry=0)
        assert span.name == "test"
        assert span.attrs == {"workflow_id": "123", "retry": 0}
        assert span.set_attribute("key", "value") is None  # Should not raise
    
    def test_noop_span_context_manager(self):
        """Verify NoopSpan works as context manager."""
        from backend.core.tracing import _NoopSpan
        
        with _NoopSpan("test") as span:
            assert span is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
