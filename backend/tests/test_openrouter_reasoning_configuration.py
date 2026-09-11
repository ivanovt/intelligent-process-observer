"""Focused tests for private Observation Reasoning OpenRouter settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.infrastructure.openrouter.composition import build_reasoning_agent, build_reasoning_model


def test_reasoning_openrouter_defaults_are_optional_at_application_startup() -> None:
    """Unrelated startup does not require a model credential."""
    settings = Settings(openrouter_api_key=None)
    assert settings.openrouter_api_key is None
    assert settings.observation_reasoning_model == "openai/gpt-5.6-terra"
    assert settings.openrouter_request_timeout_seconds == 120
    assert settings.observation_reasoning_max_output_tokens == 12_288
    assert settings.openrouter_allow_fallbacks is True
    assert settings.openrouter_provider_order == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("openrouter_request_timeout_seconds", 0),
        ("openrouter_request_timeout_seconds", -0.5),
        ("observation_reasoning_max_output_tokens", 0),
        ("observation_reasoning_max_output_tokens", -1),
    ],
)
def test_reasoning_openrouter_bounds_must_be_positive(field: str, value: float) -> None:
    """Timeout and output bounds reject zero and negative values."""
    with pytest.raises(ValidationError):
        Settings(**{field: value})


@pytest.mark.parametrize(
    ("timeout", "max_output_tokens"),
    [(0.25, 1), (321.5, 99_999)],
)
def test_reasoning_openrouter_accepts_arbitrary_positive_limits(
    timeout: float, max_output_tokens: int
) -> None:
    """Reasoning request limits retain explicitly configured positive values."""
    settings = Settings(
        openrouter_request_timeout_seconds=timeout,
        observation_reasoning_max_output_tokens=max_output_tokens,
    )
    assert settings.openrouter_request_timeout_seconds == timeout
    assert settings.observation_reasoning_max_output_tokens == max_output_tokens


def test_reasoning_openrouter_composition_uses_the_configured_model_name() -> None:
    """Composition retains an explicit reasoning-model override."""
    model = build_reasoning_model(
        Settings(
            openrouter_api_key="test-composition-credential",
            observation_reasoning_model="vendor/model-override",
        )
    )
    assert model.model_name == "vendor/model-override"


def test_reasoning_agent_composition_applies_configured_request_limits() -> None:
    """The production adapter receives both model and request settings from Settings."""
    agent = build_reasoning_agent(
        Settings(
            openrouter_api_key="test-composition-credential",
            observation_reasoning_model="vendor/model-override",
            openrouter_request_timeout_seconds=321.5,
            observation_reasoning_max_output_tokens=99_999,
        )
    )

    assert agent._model.model_name == "vendor/model-override"
    assert agent._settings == {"timeout": 321.5, "max_tokens": 99_999}


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


@pytest.mark.parametrize(
    "providers",
    [[], ["first", "second", "third"]],
)
def test_enabled_fallback_accepts_zero_or_ordered_multiple_providers(
    providers: list[str],
) -> None:
    """Enabled fallback permits no explicit pinning or an ordered preference list."""
    settings = Settings(openrouter_allow_fallbacks=True, openrouter_provider_order=providers)
    assert settings.openrouter_provider_order == providers


@pytest.mark.parametrize(
    "providers",
    [["duplicate", "duplicate"], [""], ["valid", "   "]],
)
def test_provider_order_rejects_duplicates_and_blank_entries(providers: list[str]) -> None:
    """Provider routing identifiers must be unique and non-blank."""
    with pytest.raises(ValidationError):
        Settings(openrouter_provider_order=providers)


def test_composition_requires_a_non_blank_secret_without_disclosing_it() -> None:
    """Missing or blank credentials fail safely at model composition time only."""
    for key in (None, " "):
        settings = Settings(openrouter_api_key=key)
        with pytest.raises(ValueError) as error:
            build_reasoning_model(settings)
        assert "credential" in str(error.value).lower()
        assert "secret" not in str(error.value).lower()


@pytest.mark.parametrize(
    ("allow_fallbacks", "providers", "expected_policy"),
    [
        (True, [], {"allow_fallbacks": True}),
        (True, ["first", "second"], {"allow_fallbacks": True, "order": ["first", "second"]}),
        (False, ["pinned"], {"allow_fallbacks": False, "order": ["pinned"]}),
    ],
)
def test_composition_projects_exact_provider_policy(
    allow_fallbacks: bool, providers: list[str], expected_policy: dict[str, object]
) -> None:
    """Native model settings contain only the configured OpenRouter routing policy."""
    model = build_reasoning_model(
        Settings(
            openrouter_api_key="test-composition-credential",
            openrouter_allow_fallbacks=allow_fallbacks,
            openrouter_provider_order=providers,
        )
    )
    assert model.settings == {"extra_body": {"provider": expected_policy}}


def test_credential_never_appears_in_configuration_or_composed_model_representations() -> None:
    """Credential-bearing settings and native composition objects keep the key private."""
    credential = "configuration-secret-must-not-leak"
    settings = Settings(openrouter_api_key=credential)
    model = build_reasoning_model(settings)
    rendered = " ".join((repr(settings), repr(model), repr(model.provider)))
    assert credential not in rendered
