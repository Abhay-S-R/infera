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
    CoverageEvaluation,
    ResearchAgenda,
)
from backend.integrations.llm import generate, generate_structured
from backend.core.budget import check_budget_or_stop, get_budget
from backend.core.events import publish_event
from backend.core.logger import get_logger
from backend.core.tracing import trace_agent
from backend.agents.state import PipelineState
from backend.agents.tools.web_search import search_web
from backend.agents.tools.url_scraper import scrape_url
from backend.pipeline.context import competitor_profile_prompt_block

logger = get_logger("scout")

AGENDA_GENERATION_PROMPT = """You are a strategic competitive intelligence analyst.

Given this signal and competitor history, list the 5 research questions that would most change our strategic assessment. 
Not search keyword variants. 
Examples: pricing direction, build vs buy, which customer segments threatened, who built it, what they cut to ship, hiring signals for roadmap.
Return a structured ResearchAgenda."""

COVERAGE_EVAL_PROMPT = """You are a Senior Research Editor.
Review the synthesized research findings against the original signal.
Determine if the research adequately covers the strategic angles (Pricing, Team, Build vs Buy, GTM).
If the research is lacking in key areas or has unanswered questions, list the missing questions and assign a confidence score < 0.75.
If the research is comprehensive, assign a confidence score >= 0.75.
"""

SYNTHESIS_SYSTEM_PROMPT = """You are the Scout agent — a competitive intelligence researcher.

You have just completed web research on a competitive signal guided by a strategic Research Agenda. Your job is to:
1. Synthesize all the findings from multiple search results to explicitly answer the agenda questions.
2. Identify the most important facts, numbers, and quotes.
3. Note any conflicting information across sources.
4. Summarize everything into a clear, evidence-based research brief structured around the agenda questions.
Format answers as: "Agenda Q1: ... Answer: ..."

Be factual. Cite specifics (numbers, dates, names). Don't speculate — report what the sources say."""


@trace_agent("scout")
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
    current_angle = state.get("current_angle", "General Investigation")

    # Check if Arbiter sent us back with specific retry queries
    validation = state.get("validation_result")
    retry_queries = None
    if validation and validation.retry_with_queries:
        retry_queries = validation.retry_with_queries

    competitor_profile = state.get("competitor_profile")
    agenda = None

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

    # ─── Setup Adaptive Loop ───
    MAX_SCOUT_LOOPS = 2
    loop_count = 0
    
    all_results: list[SearchResult] = []
    scraped_content: list[str] = []
    all_queries_used: list[str] = []
    seen_urls = set()

    if retry_queries:
        queries = retry_queries
        wf_logger.info("scout_using_retry_queries", queries=queries)
    else:
        agenda = await _generate_agenda(signal, sentinel_output, competitor_profile, current_angle, budget=budget)
        queries = [q.question for q in sorted(agenda.questions, key=lambda x: x.priority, reverse=True)[:5]]
        wf_logger.info("scout_agenda_generated", queries=queries)

    try:
        while loop_count < MAX_SCOUT_LOOPS:
            loop_count += 1
            all_queries_used.extend(queries)

            await publish_event("agent_activity", {
                "agent": "scout",
                "status": "running",
                "message": f"Loop {loop_count}: Executing {len(queries)} search queries",
                "detail": "; ".join(queries[:3]),
                "workflow_id": workflow_id,
            })

            # ─── Step 2: Execute searches in parallel ───
            search_tasks = [search_web(q, max_results=4) for q in queries]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

            new_results = []
            for i, result in enumerate(search_results):
                if isinstance(result, Exception):
                    wf_logger.warning("scout_search_failed", query=queries[i], error=str(result))
                    continue
                new_results.extend(result)

            # Deduplicate by URL
            for r in new_results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)

            wf_logger.info("scout_search_complete", total_results=len(all_results), new_results=len(new_results))

            await publish_event("agent_activity", {
                "agent": "scout",
                "status": "running",
                "message": f"Found {len(all_results)} total unique sources",
                "detail": f"Scraping top results for full content...",
                "workflow_id": workflow_id,
            })

            # ─── Step 3: Scrape top 3 URLs for fuller content ───
            top_results = sorted(all_results, key=lambda r: r.relevance, reverse=True)[:3]
            
            # Only scrape if we haven't already
            scraped_content = []
            for result in top_results:
                try:
                    content = await scrape_url(result.url, max_chars=3000)
                    if content and len(content) > 100:
                        scraped_content.append(f"### {result.title}\\nSource: {result.url}\\n\\n{content[:2000]}")
                except Exception as e:
                    wf_logger.warning("scout_scrape_failed", url=result.url, error=str(e))

            # ─── Step 4: Synthesize findings with LLM ───
            synthesis_prompt = _build_synthesis_prompt(signal, sentinel_output, all_results, scraped_content, agenda)

            research_output, _usage = await generate_structured(
                prompt=synthesis_prompt,
                response_model=ResearchOutput,
                system=SYNTHESIS_SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=8192,
                budget=budget,
                agent="scout",
            )

            research_output.queries_used = all_queries_used
            research_output.results = all_results[:15]
            research_output.sources_consulted = len(all_results)
            if agenda:
                research_output.agenda = agenda
            
            if loop_count >= MAX_SCOUT_LOOPS:
                break
                
            # ─── Step 5: Evaluate Coverage ───
            eval_prompt = f"Original Signal: {signal.title}\\nType: {sentinel_output.event_type}\\n\\nCurrent Research Summary:\\n{research_output.raw_content_summary}\\n\\nKey Findings:\\n{'; '.join(research_output.key_findings)}\\n\\nEvaluate the coverage."
            
            try:
                coverage_eval, _eval_usage = await generate_structured(
                    prompt=eval_prompt,
                    response_model=CoverageEvaluation,
                    system=COVERAGE_EVAL_PROMPT,
                    temperature=0.3,
                    budget=budget,
                    agent="scout"
                )
                
                wf_logger.info("scout_coverage_eval", confidence=coverage_eval.confidence, missing_questions=coverage_eval.missing_questions)
                
                if coverage_eval.confidence >= 0.75 or not coverage_eval.missing_questions:
                    break
                    
                # If confidence is low, we generate new queries based on missing questions
                queries = coverage_eval.missing_questions[:3] # Take up to 3 missing questions
                
            except Exception as e:
                wf_logger.warning("scout_coverage_eval_failed", error=str(e))
                break # Break on eval error to be safe

        # Outside the loop, return the final research_output
        wf_logger.info(
            "scout_completed",
            findings=len(research_output.key_findings),
            sources=research_output.sources_consulted,
            loops=loop_count
        )

        await publish_event("agent_activity", {
            "agent": "scout",
            "status": "done",
            "message": f"Research complete after {loop_count} loops: {len(research_output.key_findings)} findings from {research_output.sources_consulted} sources",
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


async def _generate_agenda(
    signal,
    sentinel_output: SentinelOutput,
    competitor_profile,
    current_angle: str,
    budget=None,
) -> ResearchAgenda:
    """Generate a targeted research agenda based on the signal and competitor profile."""
    prompt = (
        f"Signal: {signal.title}\n"
        f"Event Type: {sentinel_output.event_type}\n"
        f"Entities: {', '.join(sentinel_output.entities)}\n"
        f"Investigation Angle: {current_angle}\n"
        f"Summary: {sentinel_output.summary}\n"
    )
    if signal.custom_question:
        prompt += f"User's Question: {signal.custom_question}\n"

    if competitor_profile:
        mem_block = competitor_profile_prompt_block(competitor_profile)
        if mem_block:
            prompt += f"\n{mem_block}\n"

    try:
        agenda, _usage = await generate_structured(
            prompt=prompt,
            response_model=ResearchAgenda,
            system=AGENDA_GENERATION_PROMPT,
            temperature=0.5,
            model="llama-3.3-70b-versatile",
            budget=budget,
            agent="scout",
        )
        return agenda
    except Exception as e:
        logger.warning("scout_agenda_generation_fallback", error=str(e))

    # Fallback agenda
    from backend.models.schemas import ResearchQuestion
    base = signal.title
    entities = sentinel_output.entities
    fallback_questions = [
        ResearchQuestion(question=base, why_it_matters="Basic coverage", priority=5)
    ]
    if entities:
        fallback_questions.append(
            ResearchQuestion(question=f"What is the market impact of {entities[0]} {sentinel_output.event_type}?", why_it_matters="Assess impact", priority=4)
        )
    fallback_questions.append(
        ResearchQuestion(question=f"How does {base} affect competitors?", why_it_matters="Competitive landscape", priority=3)
    )
    return ResearchAgenda(questions=fallback_questions)


def _build_synthesis_prompt(
    signal, sentinel_output: SentinelOutput,
    results: list[SearchResult], scraped_content: list[str],
    agenda: ResearchAgenda | None = None
) -> str:
    """Build the synthesis prompt from search results and scraped content."""
    prompt = (
        f"## Original Signal\n"
        f"**Title:** {signal.title}\n"
        f"**Type:** {sentinel_output.event_type}\n"
        f"**Entities:** {', '.join(sentinel_output.entities)}\n"
        f"**Sentinel Summary:** {sentinel_output.summary}\n\n"
    )
    
    if agenda and agenda.questions:
        prompt += "## Research Agenda\n"
        for i, q in enumerate(agenda.questions, 1):
            prompt += f"Q{i}: {q.question}\n"
        prompt += "\n"

    prompt += f"## Search Results ({len(results)} found)\n\n"

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
