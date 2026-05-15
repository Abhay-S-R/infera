"""
ASCENT Scout Agent — deep web research for competitive intelligence.

The Scout is the second agent in the pipeline. After Sentinel flags a signal
as worth investigating, Scout:
  1. Generates 3-5 targeted search queries based on the signal
  2. Executes web searches via Tavily API
  3. Optionally scrapes top URLs for full content
  4. Structures all findings into a ResearchOutput

Dev 2 owns this file.
"""
import asyncio
from backend.models.schemas import (
    ResearchOutput,
    SearchResult,
    SentinelOutput,
    ActivityEvent,
    AgentStatus,
)
from backend.services.llm import generate, generate_structured
from backend.services.budget import check_budget_or_stop, get_budget
from backend.services.events import publish_event
from backend.services.logger import get_logger
from backend.agents.state import PipelineState
from backend.agents.tools.web_search import search_web
from backend.agents.tools.url_scraper import scrape_url

logger = get_logger("scout")

QUERY_GENERATION_PROMPT = """You are a competitive intelligence research specialist.

Given a signal that has been flagged for investigation, generate {num_queries} diverse web search queries
that will help gather comprehensive competitive intelligence about this signal.

The queries should cover:
- The core event/announcement itself
- Competitor reactions and market response
- Historical context and trend implications
- Technical or strategic details

Return ONLY a JSON array of query strings, nothing else.
Example: ["query one", "query two", "query three"]"""

SYNTHESIS_SYSTEM_PROMPT = """You are the Scout agent — a competitive intelligence researcher.

You have just completed web research on a competitive signal. Your job is to:
1. Synthesize all the findings from multiple search results into key findings
2. Identify the most important facts, numbers, and quotes
3. Note any conflicting information across sources
4. Summarize everything into a clear, evidence-based research brief

Be factual. Cite specifics (numbers, dates, names). Don't speculate — report what the sources say."""


async def scout_node(state: PipelineState) -> dict:
    """
    Scout agent node for LangGraph.

    Takes SentinelOutput from state, generates search queries,
    executes web searches, and returns structured ResearchOutput.
    """
    sentinel_output: SentinelOutput = state["sentinel_output"]
    signal = state["signal"]
    workflow_id = state.get("workflow_id", "unknown")
    retry_count = state.get("retry_count", 0)

    # Check if Arbiter sent us back with specific retry queries
    validation = state.get("validation_result")
    retry_queries = None
    if validation and validation.retry_with_queries:
        retry_queries = validation.retry_with_queries

    wf_logger = logger.with_context(workflow_id=workflow_id, retry=retry_count)
    wf_logger.info("scout_started", title=signal.title)

    stopped = check_budget_or_stop(state, "scout", workflow_id)
    if stopped:
        stopped["budget_exceeded"] = True
        return stopped

    budget = get_budget(state)

    await publish_event("agent_activity", {
        "agent": "scout",
        "status": "running",
        "message": f"{'Re-researching' if retry_count > 0 else 'Researching'}: {signal.title[:80]}",
        "detail": f"Retry #{retry_count}" if retry_count > 0 else "Initial research",
        "workflow_id": workflow_id,
    })

    # ─── Step 1: Generate search queries ───
    if retry_queries:
        queries = retry_queries
        wf_logger.info("scout_using_retry_queries", queries=queries)
    else:
        queries = await _generate_queries(signal, sentinel_output, num_queries=4, budget=budget)
        wf_logger.info("scout_queries_generated", queries=queries)

    await publish_event("agent_activity", {
        "agent": "scout",
        "status": "running",
        "message": f"Executing {len(queries)} search queries",
        "detail": "; ".join(queries[:3]),
        "workflow_id": workflow_id,
    })

    # ─── Step 2: Execute searches in parallel ───
    all_results: list[SearchResult] = []
    search_tasks = [search_web(q, max_results=4) for q in queries]
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

    for i, result in enumerate(search_results):
        if isinstance(result, Exception):
            wf_logger.warning("scout_search_failed", query=queries[i], error=str(result))
            continue
        all_results.extend(result)

    # Deduplicate by URL
    seen_urls = set()
    unique_results = []
    for r in all_results:
        if r.url not in seen_urls:
            seen_urls.add(r.url)
            unique_results.append(r)
    all_results = unique_results

    wf_logger.info("scout_search_complete", total_results=len(all_results))

    await publish_event("agent_activity", {
        "agent": "scout",
        "status": "running",
        "message": f"Found {len(all_results)} unique sources",
        "detail": f"Scraping top results for full content...",
        "workflow_id": workflow_id,
    })

    # ─── Step 3: Scrape top 3 URLs for fuller content ───
    top_results = sorted(all_results, key=lambda r: r.relevance, reverse=True)[:3]
    scraped_content = []

    for result in top_results:
        try:
            content = await scrape_url(result.url, max_chars=3000)
            if content and len(content) > 100:
                scraped_content.append(f"### {result.title}\nSource: {result.url}\n\n{content[:2000]}")
        except Exception as e:
            wf_logger.warning("scout_scrape_failed", url=result.url, error=str(e))

    # ─── Step 4: Synthesize findings with LLM ───
    synthesis_prompt = _build_synthesis_prompt(signal, sentinel_output, all_results, scraped_content)

    try:
        research_output, _usage = await generate_structured(
            prompt=synthesis_prompt,
            response_model=ResearchOutput,
            system=SYNTHESIS_SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=8192,
            budget=budget,
            agent="scout",
        )

        # Override with actual data
        research_output.queries_used = queries
        research_output.results = all_results[:15]  # Cap to avoid context blowup
        research_output.sources_consulted = len(all_results)

        wf_logger.info(
            "scout_completed",
            findings=len(research_output.key_findings),
            sources=research_output.sources_consulted,
        )

        await publish_event("agent_activity", {
            "agent": "scout",
            "status": "done",
            "message": f"Research complete: {len(research_output.key_findings)} key findings from {research_output.sources_consulted} sources",
            "workflow_id": workflow_id,
        })

        return {
            "research_output": research_output,
            "current_agent": "scout",
            "retry_count": retry_count + 1 if retry_count > 0 else retry_count,
            **budget.state_updates(),
            "activity_log": [ActivityEvent(
                agent="scout",
                status=AgentStatus.DONE,
                message=f"Research complete: {research_output.sources_consulted} sources, {len(research_output.key_findings)} findings",
                workflow_id=workflow_id,
            )],
        }

    except Exception as e:
        wf_logger.error("scout_synthesis_failed", error=str(e))

        await publish_event("agent_activity", {
            "agent": "scout",
            "status": "error",
            "message": f"Scout failed: {str(e)[:100]}",
            "workflow_id": workflow_id,
        })

        # Return raw results even if synthesis failed
        return {
            "research_output": ResearchOutput(
                queries_used=queries,
                results=all_results[:10],
                key_findings=[r.snippet for r in all_results[:5]],
                sources_consulted=len(all_results),
                raw_content_summary=f"LLM synthesis failed. Raw results from {len(all_results)} sources available.",
            ),
            "current_agent": "scout",
            **budget.state_updates(),
            "error": f"Scout synthesis error: {str(e)}",
            "activity_log": [ActivityEvent(
                agent="scout",
                status=AgentStatus.ERROR,
                message=f"Partial results: {len(all_results)} sources gathered, synthesis failed",
                workflow_id=workflow_id,
            )],
        }


async def _generate_queries(
    signal,
    sentinel_output: SentinelOutput,
    num_queries: int = 4,
    budget=None,
) -> list[str]:
    """Generate targeted search queries based on the signal and sentinel analysis."""
    prompt = (
        f"Signal: {signal.title}\n"
        f"Event Type: {sentinel_output.event_type}\n"
        f"Entities: {', '.join(sentinel_output.entities)}\n"
        f"Summary: {sentinel_output.summary}\n"
    )
    if signal.custom_question:
        prompt += f"User's Question: {signal.custom_question}\n"

    prompt += f"\nGenerate {num_queries} diverse search queries for competitive intelligence research."

    try:
        raw, _usage = await generate(
            prompt=prompt,
            system=QUERY_GENERATION_PROMPT.format(num_queries=num_queries),
            temperature=0.5,
            model="llama-3.3-70b-versatile",
            budget=budget,
            agent="scout",
        )
        # Parse the JSON array from the response
        import json
        # Strip markdown code fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
            clean = clean.rsplit("```", 1)[0]
        queries = json.loads(clean.strip())

        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            return queries[:num_queries]
    except Exception as e:
        logger.warning("scout_query_generation_fallback", error=str(e))

    # Fallback: generate basic queries from signal data
    base = signal.title
    entities = sentinel_output.entities
    fallback = [base]
    if entities:
        fallback.append(f"{entities[0]} competitive analysis 2026")
        fallback.append(f"{entities[0]} market impact {sentinel_output.event_type}")
    fallback.append(f"{base} industry reaction")
    return fallback[:num_queries]


def _build_synthesis_prompt(
    signal, sentinel_output: SentinelOutput,
    results: list[SearchResult], scraped_content: list[str]
) -> str:
    """Build the synthesis prompt from search results and scraped content."""
    prompt = (
        f"## Original Signal\n"
        f"**Title:** {signal.title}\n"
        f"**Type:** {sentinel_output.event_type}\n"
        f"**Entities:** {', '.join(sentinel_output.entities)}\n"
        f"**Sentinel Summary:** {sentinel_output.summary}\n\n"
        f"## Search Results ({len(results)} found)\n\n"
    )

    for i, r in enumerate(results[:10], 1):
        prompt += f"{i}. **{r.title}** (relevance: {r.relevance:.2f})\n"
        prompt += f"   URL: {r.url}\n"
        prompt += f"   {r.snippet[:200]}\n\n"

    if scraped_content:
        prompt += f"\n## Full Article Content (top {len(scraped_content)} sources)\n\n"
        prompt += "\n\n---\n\n".join(scraped_content)

    prompt += (
        "\n\n## Your Task\n"
        "Synthesize all the above into a structured research output. "
        "Extract the key findings (5-10 bullet points), and write a comprehensive "
        "raw content summary that captures all important details from the sources."
    )

    return prompt
