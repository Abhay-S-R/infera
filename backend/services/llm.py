"""
ASCENT LLM Service — Gemini & Groq API wrapper.

All agents call this module for LLM inference.
It dynamically routes to Groq (for speed) or Gemini (for complex reasoning) based on the model name.

Usage:
    from backend.services.llm import generate, generate_structured

    # Groq text generation
    text = await generate("Summarize...", model="llama-3.3-70b-versatile")

    # Gemini structured output
    result = await generate_structured(
        prompt="Analyze this signal...",
        response_model=AnalysisOutput,
        model="gemini-3.1-flash-lite"
    )
"""
import asyncio
import json
import time
from typing import Optional, TypeVar, Type

from google import genai
from google.genai import types
from groq import AsyncGroq
from pydantic import BaseModel

from backend.config import settings
from backend.services.logger import get_logger

logger = get_logger("llm")

# ─── Type var for structured output generics ───
T = TypeVar("T", bound=BaseModel)

# ─── Client singletons ───
_gemini_client: Optional[genai.Client] = None
_groq_client: Optional[AsyncGroq] = None

# ─── Model configuration ───
DEFAULT_MODEL = "gemini-3.1-flash-lite"
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0  # seconds


def _get_gemini_client() -> genai.Client:
    """Lazy-initialize the Gemini client."""
    global _gemini_client
    if _gemini_client is None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("gemini_client_initialized")
    return _gemini_client


def _get_groq_client() -> AsyncGroq:
    """Lazy-initialize the Groq client."""
    global _groq_client
    if _groq_client is None:
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set.")
        _groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        logger.info("groq_client_initialized")
    return _groq_client


def _is_groq_model(model: str) -> bool:
    return model.startswith("llama") or model.startswith("mixtral") or model.startswith("gemma")


async def generate(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_output_tokens: int = 4096,
) -> str:
    """Generate plain text using either Groq or Gemini."""
    
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
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                    "completion_tokens": response.usage.completion_tokens if response.usage else None,
                }
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
                usage = _extract_gemini_usage(response)

            elapsed = time.monotonic() - start
            logger.info(
                "llm_generate_success",
                model=model,
                attempt=attempt,
                elapsed_s=round(elapsed, 3),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                char_count=len(text),
            )
            return text

        except Exception as e:
            last_error = e
            elapsed = time.monotonic() - start
            logger.warning(
                "llm_generate_retry",
                model=model,
                attempt=attempt,
                elapsed_s=round(elapsed, 3),
                error=str(e),
            )
            if attempt < MAX_RETRIES:
                delay = BASE_RETRY_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

    logger.error("llm_generate_failed", model=model, error=str(last_error))
    raise RuntimeError(f"LLM generation failed after {MAX_RETRIES} retries: {last_error}")


async def generate_structured(
    prompt: str,
    response_model: Type[T],
    *,
    system: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.4,
    max_output_tokens: int = 4096,
) -> T:
    """Generate structured Pydantic response using either Groq or Gemini."""
    
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        start = time.monotonic()
        try:
            if _is_groq_model(model):
                client = _get_groq_client()
                
                # Append instruction to output JSON matching the schema
                json_system = f"You must output valid JSON matching this schema:\n{json.dumps(response_model.model_json_schema())}"
                if system:
                    system_content = f"{system}\n\n{json_system}"
                else:
                    system_content = json_system
                    
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ]
                
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=max_output_tokens,
                    response_format={"type": "json_object"}
                )
                
                raw_text = response.choices[0].message.content or "{}"
                result = response_model.model_validate_json(raw_text)
                
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                    "completion_tokens": response.usage.completion_tokens if response.usage else None,
                }
                
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
                    
                usage = _extract_gemini_usage(response)

            elapsed = time.monotonic() - start
            logger.info(
                "llm_structured_success",
                model=model,
                schema=response_model.__name__,
                attempt=attempt,
                elapsed_s=round(elapsed, 3),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )
            return result

        except Exception as e:
            last_error = e
            elapsed = time.monotonic() - start
            logger.warning(
                "llm_structured_retry",
                model=model,
                schema=response_model.__name__,
                attempt=attempt,
                elapsed_s=round(elapsed, 3),
                error=str(e),
            )
            if attempt < MAX_RETRIES:
                delay = BASE_RETRY_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

    logger.error("llm_structured_failed", model=model, schema=response_model.__name__, error=str(last_error))
    raise RuntimeError(f"Structured LLM generation failed after {MAX_RETRIES} retries: {last_error}")


def _extract_gemini_usage(response) -> dict:
    """Extract token usage from Gemini response, safely."""
    usage = {}
    try:
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            usage["prompt_tokens"] = getattr(meta, "prompt_token_count", None)
            usage["completion_tokens"] = getattr(meta, "candidates_token_count", None)
    except Exception:
        pass
    return usage
