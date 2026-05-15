"""
ASCENT LLM Service — Gemini & Groq API wrapper.

All agents call this module for LLM inference.
It dynamically routes to Groq (for speed) or Gemini (for complex reasoning) based on the model name.

Usage:
    from backend.services.llm import generate, generate_structured, LLMUsage

    text, usage = await generate("Summarize...", model="llama-3.3-70b-versatile")

    result, usage = await generate_structured(
        prompt="Analyze this signal...",
        response_model=AnalysisOutput,
        model="gemini-3.1-flash-lite",
        budget=budget,
        agent="strategist",
    )
"""
from __future__ import annotations
import asyncio
import json
import time
from dataclasses import dataclass
from typing import Optional, TypeVar, Type, TYPE_CHECKING

from google import genai
from google.genai import types
from groq import AsyncGroq
from pydantic import BaseModel

from backend.config import settings
from backend.services.budget import BudgetExceededError
from backend.services.logger import get_logger

if TYPE_CHECKING:
    from backend.services.budget import TokenBudget

logger = get_logger("llm")

T = TypeVar("T", bound=BaseModel)

_gemini_client: Optional[genai.Client] = None
_groq_client: Optional[AsyncGroq] = None

DEFAULT_MODEL = "gemini-3.1-flash-lite"
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    @classmethod
    def from_counts(
        cls,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
    ) -> LLMUsage:
        p = prompt_tokens or 0
        c = completion_tokens or 0
        total = p + c
        cost = (total / 1000.0) * 0.0004
        return cls(
            prompt_tokens=p,
            completion_tokens=c,
            total_tokens=total,
            estimated_cost_usd=cost,
        )


def _get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("gemini_client_initialized")
    return _gemini_client


def _get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set.")
        _groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        logger.info("groq_client_initialized")
    return _groq_client


def _is_groq_model(model: str) -> bool:
    return model.startswith("llama") or model.startswith("mixtral") or model.startswith("gemma")


def _check_budget_before_call(budget: Optional["TokenBudget"], agent: Optional[str]) -> None:
    if budget is None:
        return
    if budget.is_exceeded():
        raise BudgetExceededError(
            f"Budget exceeded before {agent or 'llm'} call "
            f"({budget.tokens_used:,}/{budget.max_tokens:,} tokens)"
        )


def _apply_usage_to_budget(
    budget: Optional["TokenBudget"],
    agent: Optional[str],
    usage: LLMUsage,
) -> None:
    if budget is None or usage.total_tokens <= 0:
        return
    budget.track(agent or "llm", usage.total_tokens, usage.estimated_cost_usd)


async def generate(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_output_tokens: int = 4096,
    budget: Optional["TokenBudget"] = None,
    agent: Optional[str] = None,
) -> tuple[str, LLMUsage]:
    """Generate plain text; returns (text, usage)."""
    _check_budget_before_call(budget, agent)

    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        start = time.monotonic()
        try:
            if _is_groq_model(model):
                client = _get_groq_client()
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})

                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=max_output_tokens,
                )
                text = response.choices[0].message.content or ""
                usage = LLMUsage.from_counts(
                    response.usage.prompt_tokens if response.usage else None,
                    response.usage.completion_tokens if response.usage else None,
                )
            else:
                client = _get_gemini_client()
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
                if system:
                    config.system_instruction = system

                response = await client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                text = response.text or ""
                raw = _extract_gemini_usage(response)
                usage = LLMUsage.from_counts(
                    raw.get("prompt_tokens"),
                    raw.get("completion_tokens"),
                )

            _apply_usage_to_budget(budget, agent, usage)

            elapsed = time.monotonic() - start
            logger.info(
                "llm_generate_success",
                model=model,
                agent=agent,
                attempt=attempt,
                elapsed_s=round(elapsed, 3),
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                char_count=len(text),
            )
            return text, usage

        except BudgetExceededError:
            raise
        except Exception as e:
            last_error = e
            elapsed = time.monotonic() - start
            logger.warning(
                "llm_generate_retry",
                model=model,
                agent=agent,
                attempt=attempt,
                elapsed_s=round(elapsed, 3),
                error=str(e),
            )
            if attempt < MAX_RETRIES:
                delay = BASE_RETRY_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

    logger.error("llm_generate_failed", model=model, agent=agent, error=str(last_error))
    raise RuntimeError(f"LLM generation failed after {MAX_RETRIES} retries: {last_error}")


async def generate_structured(
    prompt: str,
    response_model: Type[T],
    *,
    system: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.4,
    max_output_tokens: int = 4096,
    budget: Optional["TokenBudget"] = None,
    agent: Optional[str] = None,
) -> tuple[T, LLMUsage]:
    """Generate structured Pydantic response; returns (result, usage)."""
    _check_budget_before_call(budget, agent)

    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        start = time.monotonic()
        try:
            if _is_groq_model(model):
                client = _get_groq_client()

                json_system = (
                    f"You must output valid JSON matching this schema:\n"
                    f"{json.dumps(response_model.model_json_schema())}"
                )
                system_content = f"{system}\n\n{json_system}" if system else json_system

                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt},
                ]

                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=max_output_tokens,
                    response_format={"type": "json_object"},
                )

                raw_text = response.choices[0].message.content or "{}"
                result = response_model.model_validate_json(raw_text)
                usage = LLMUsage.from_counts(
                    response.usage.prompt_tokens if response.usage else None,
                    response.usage.completion_tokens if response.usage else None,
                )

            else:
                client = _get_gemini_client()
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=response_model,
                )
                if system:
                    config.system_instruction = system

                response = await client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )

                if hasattr(response, "parsed") and response.parsed is not None:
                    result = response.parsed
                else:
                    raw_text = response.text or "{}"
                    data = json.loads(raw_text)
                    result = response_model.model_validate(data)

                raw = _extract_gemini_usage(response)
                usage = LLMUsage.from_counts(
                    raw.get("prompt_tokens"),
                    raw.get("completion_tokens"),
                )

            _apply_usage_to_budget(budget, agent, usage)

            elapsed = time.monotonic() - start
            logger.info(
                "llm_structured_success",
                model=model,
                schema=response_model.__name__,
                agent=agent,
                attempt=attempt,
                elapsed_s=round(elapsed, 3),
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
            return result, usage

        except BudgetExceededError:
            raise
        except Exception as e:
            last_error = e
            elapsed = time.monotonic() - start
            logger.warning(
                "llm_structured_retry",
                model=model,
                schema=response_model.__name__,
                agent=agent,
                attempt=attempt,
                elapsed_s=round(elapsed, 3),
                error=str(e),
            )
            if attempt < MAX_RETRIES:
                delay = BASE_RETRY_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

    logger.error(
        "llm_structured_failed",
        model=model,
        schema=response_model.__name__,
        agent=agent,
        error=str(last_error),
    )
    raise RuntimeError(f"Structured LLM generation failed after {MAX_RETRIES} retries: {last_error}")


def _extract_gemini_usage(response) -> dict:
    usage = {}
    try:
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            usage["prompt_tokens"] = getattr(meta, "prompt_token_count", None)
            usage["completion_tokens"] = getattr(meta, "candidates_token_count", None)
    except Exception:
        pass
    return usage
