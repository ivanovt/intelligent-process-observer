"""Compose the injected PydanticAI OpenRouter model without exposing credentials."""

# ruff: noqa: E501
from __future__ import annotations

from app.core.settings import Settings


def build_reasoning_model(settings: Settings):
    """Return one configured native OpenRouter model or fail without secret disclosure."""
    if (
        settings.openrouter_api_key is None
        or not settings.openrouter_api_key.get_secret_value().strip()
    ):
        raise ValueError("OpenRouter credential is required for reasoning model composition")
    from pydantic_ai.models.openrouter import OpenRouterModel
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    provider = OpenRouterProvider(api_key=settings.openrouter_api_key.get_secret_value())
    policy = {"allow_fallbacks": settings.openrouter_allow_fallbacks}
    if settings.openrouter_provider_order:
        policy["order"] = settings.openrouter_provider_order
    return OpenRouterModel(
        settings.observation_reasoning_model,
        provider=provider,
        settings={"extra_body": {"provider": policy}},
    )
