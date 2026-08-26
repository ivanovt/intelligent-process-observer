"""Shared OpenRouter Chat Completions client construction; no domain imports."""

from __future__ import annotations

import os
from typing import Protocol

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


class OpenRouterSettings(Protocol):
    model: str
    base_url: str
    provider_order: tuple[str, ...]
    allow_provider_fallbacks: bool
    reasoning_effort: str
    max_output_tokens: int
    model_timeout_seconds: float
    parallel_tool_calls: bool
    provider_retries: int


def provider_preferences(settings: OpenRouterSettings) -> dict[str, object]:
    preferences: dict[str, object] = {"allow_fallbacks": settings.allow_provider_fallbacks}
    if settings.provider_order:
        preferences["order"] = list(settings.provider_order)
    return preferences


def build_pydantic_openrouter_model(
    settings: OpenRouterSettings, *, api_key: str | None = None
) -> OpenAIChatModel:
    client = AsyncOpenAI(
        api_key=api_key or os.environ.get("OPENROUTER_KEY"),
        base_url=settings.base_url,
        timeout=settings.model_timeout_seconds,
        max_retries=settings.provider_retries,
    )
    return OpenAIChatModel(settings.model, provider=OpenAIProvider(openai_client=client))


def build_langchain_openrouter_model(
    settings: OpenRouterSettings, *, api_key: str | None = None
) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.model,
        api_key=api_key or os.environ.get("OPENROUTER_KEY"),
        base_url=settings.base_url,
        use_responses_api=False,
        reasoning_effort=settings.reasoning_effort,
        max_tokens=settings.max_output_tokens,
        timeout=settings.model_timeout_seconds,
        max_retries=settings.provider_retries,
        model_kwargs={"parallel_tool_calls": settings.parallel_tool_calls},
        extra_body={"provider": provider_preferences(settings)},
    )
