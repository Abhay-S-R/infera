"""
INFERA Web Search Tool — Tavily API wrapper.
Used by the Scout agent to search the web for competitive intelligence.

Dev 2 owns this file.
"""
import httpx
from backend.core.config import settings
from backend.models.schemas import SearchResult


async def search_web(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> list[SearchResult]:
    """
    Search the web using Tavily API.

    Args:
        query: Search query string
        max_results: Maximum number of results to return (1-10)
        search_depth: "basic" or "advanced" (advanced is slower but more thorough)
        include_domains: Only search these domains
        exclude_domains: Exclude these domains from results

    Returns:
        List of SearchResult objects with title, url, snippet, relevance
    """
    if settings.DEMO_MODE:
        return _get_cached_results(query)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth,
                "include_answer": False,
            }

            if include_domains:
                payload["include_domains"] = include_domains
            if exclude_domains:
                payload["exclude_domains"] = exclude_domains

            response = await client.post(
                "https://api.tavily.com/search",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", "")[:500],
                    relevance=item.get("score", 0.5),
                )
            )

        return results

    except httpx.HTTPStatusError as e:
        print(f"[web_search] Tavily API error: {e.response.status_code}")
        return _get_cached_results(query) if settings.DEMO_MODE else []

    except Exception as e:
        print(f"[web_search] Error: {e}")
        return []


def _get_cached_results(query: str) -> list[SearchResult]:
    """Fallback cached results for demo mode — ensures the demo never crashes."""
    return [
        SearchResult(
            title=f"[CACHED] Result for: {query}",
            url="https://example.com/cached",
            snippet=f"This is a cached demo result for the query: {query}. "
                    f"In production, this would be a real Tavily search result.",
            relevance=0.8,
        )
    ]
