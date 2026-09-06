"""Focused tests for private Observation Reasoning OpenRouter settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.infrastructure.openrouter.composition import build_reasoning_model


def test_reasoning_openrouter_defaults_are_optional_at_application_startup() -> None:
    """Unrelated startup does not require a model credential."""
    settings = Settings()
    assert settings.openrouter_api_key is None
    assert settings.observation_reasoning_model == "openai/gpt-5.6-terra"
    assert settings.openrouter_request_timeout_seconds == 120
    assert settings.observation_reasoning_max_output_tokens == 12_288
    assert settings.openrouter_allow_fallbacks is True
    assert settings.openrouter_provider_order == []


@pytest.mark.parametrize(
    "field", ["openrouter_request_timeout_seconds", "observation_reasoning_max_output_tokens"]
)
def test_reasoning_openrouter_bounds_must_be_positive(field: str) -> None:
    """Timeout and output bounds reject zero and negative values."""
    with pytest.raises(ValidationError):
        Settings(**{field: 0})


def test_disabled_fallback_requires_one_unique_non_blank_provider() -> None:
    """Strict provider pinning cannot be ambiguous."""
    with pytest.raises(ValidationError):
        Settings(openrouter_allow_fallbacks=False)
    with pytest.raises(ValidationError):
        Settings(openrouter_allow_fallbacks=False, openrouter_provider_order=["a", "b"])
    with pytest.raises(ValidationError):
        Settings(openrouter_provider_order=["a", "a"])
    with pytest.raises(ValidationError):
        Settings(openrouter_provider_order=[" "])
    assert Settings(openrouter_allow_fallbacks=False, openrouter_provider_order=["pinned"])


def test_composition_requires_a_non_blank_secret_without_disclosing_it() -> None:
    """Missing or blank credentials fail safely at model composition time only."""
    for key in (None, " "):
        settings = Settings(openrouter_api_key=key)
        with pytest.raises(ValueError) as error:
            build_reasoning_model(settings)
        assert "credential" in str(error.value).lower()
        assert "secret" not in str(error.value).lower()
