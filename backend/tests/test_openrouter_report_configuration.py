"""Focused tests for private Report Generation OpenRouter configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.infrastructure.openrouter.composition import build_report_agent, build_report_model


def test_report_openrouter_defaults_are_optional_at_application_startup() -> None:
    """Report settings have fixed defaults without requiring a credential at startup."""
    settings = Settings()
    assert settings.openrouter_api_key is None
    assert settings.observation_report_model == "openai/gpt-5.6-terra"
    assert settings.observation_report_max_output_tokens == 8_192


@pytest.mark.parametrize("value", [0, -1])
def test_report_output_token_limit_must_be_positive(value: int) -> None:
    """Invalid report output bounds are rejected by settings validation."""
    with pytest.raises(ValidationError):
        Settings(observation_report_max_output_tokens=value)


def test_report_openrouter_environment_overrides_are_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deployment environment can independently select the report model and output ceiling."""
    monkeypatch.setenv("OBSERVATION_REPORT_MODEL", "vendor/report-model")
    monkeypatch.setenv("OBSERVATION_REPORT_MAX_OUTPUT_TOKENS", "5432")
    settings = Settings()
    assert settings.observation_report_model == "vendor/report-model"
    assert settings.observation_report_max_output_tokens == 5432


def test_report_composition_uses_model_limits_and_shared_routing_policy() -> None:
    """Report composition preserves the exact credential, fallback, and provider policy."""
    settings = Settings(
        openrouter_api_key="report-composition-credential",
        observation_report_model="vendor/report-model",
        observation_report_max_output_tokens=765,
        openrouter_request_timeout_seconds=43.5,
        openrouter_allow_fallbacks=False,
        openrouter_provider_order=["pinned"],
    )
    model = build_report_model(settings)
    agent = build_report_agent(settings)
    assert model.model_name == "vendor/report-model"
    assert model.settings == {
        "extra_body": {"provider": {"allow_fallbacks": False, "order": ["pinned"]}}
    }
    assert agent._model.model_name == "vendor/report-model"
    assert agent._settings == {"timeout": 43.5, "max_tokens": 765}


def test_report_composition_requires_a_secret_without_disclosing_it() -> None:
    """Missing credentials fail safely without exposing a configured secret."""
    for key in (None, " "):
        with pytest.raises(ValueError) as error:
            build_report_model(Settings(openrouter_api_key=key))
        assert "credential" in str(error.value).lower()
    secret = "report-composition-secret"
    model = build_report_model(Settings(openrouter_api_key=secret))
    assert secret not in " ".join((repr(model), repr(model.provider)))
