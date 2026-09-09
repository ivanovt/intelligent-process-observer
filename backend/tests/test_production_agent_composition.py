"""Focused production composition tests for Metric and Alert model boundaries."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.settings import Settings
from app.infrastructure.agents.pydantic_ai_alerts import PydanticAIAlertAnalysisAgent
from app.infrastructure.agents.pydantic_ai_metrics import PydanticAIMetricsAnalysisAgent
from app.infrastructure.agents.unavailable import (
    UnavailableAlertAnalysisAgent,
    UnavailableMetricsAnalysisAgent,
    UnavailableObservationReasoningAgent,
    UnavailableReportGenerationAgent,
)
from app.infrastructure.execution.composition import build_production_execution_composition
from app.infrastructure.openrouter.composition import (
    build_alert_agent,
    build_alert_model,
    build_metric_agent,
    build_metric_model,
)
from app.knowledge.contracts import KnowledgeRetrievalRequest
from app.knowledge.empty import EmptyKnowledgeRetriever
from app.metrics.contracts import MetricAgentOperationalFailure


def test_metric_and_alert_settings_have_independent_approved_defaults() -> None:
    """Metric and Alert retain separate server-only settings despite equal defaults."""
    settings = Settings()

    assert settings.metric_analysis_model == "openai/gpt-5.6-terra"
    assert settings.alert_analysis_model == "openai/gpt-5.6-terra"
    assert settings.metric_analysis_request_timeout_seconds == 120
    assert settings.alert_analysis_request_timeout_seconds == 120
    assert settings.metric_analysis_max_output_tokens == 12_288
    assert settings.alert_analysis_max_output_tokens == 12_288


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("metric_analysis_request_timeout_seconds", 0),
        ("alert_analysis_request_timeout_seconds", -1),
        ("metric_analysis_max_output_tokens", 0),
        ("alert_analysis_max_output_tokens", -1),
    ],
)
def test_metric_and_alert_limits_must_be_positive(field: str, value: int) -> None:
    """Invalid role-specific request limits are rejected before composition."""
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_role_overrides_and_request_limits_reach_only_the_selected_adapters() -> None:
    """OpenRouter composition keeps role model settings independent."""
    settings = Settings(
        openrouter_api_key="composition-test-secret",
        metric_analysis_model="vendor/metric",
        alert_analysis_model="vendor/alert",
        metric_analysis_request_timeout_seconds=11.5,
        alert_analysis_request_timeout_seconds=22.5,
        metric_analysis_max_output_tokens=111,
        alert_analysis_max_output_tokens=222,
    )

    metric = build_metric_agent(settings)
    alert = build_alert_agent(settings)

    assert build_metric_model(settings).model_name == "vendor/metric"
    assert build_alert_model(settings).model_name == "vendor/alert"
    assert metric._model.model_name == "vendor/metric"
    assert alert._model.model_name == "vendor/alert"
    assert metric._settings == {"timeout": 11.5, "max_tokens": 111}
    assert alert._settings == {"timeout": 22.5, "max_tokens": 222}


def test_lifespan_composition_uses_safe_ports_without_a_model_credential() -> None:
    """Missing OpenRouter configuration leaves startup composition and ports usable."""
    composition = build_production_execution_composition(
        settings=Settings(), session_factory=async_sessionmaker()
    )

    assert isinstance(composition.metric_agent, UnavailableMetricsAnalysisAgent)
    assert isinstance(composition.alert_agent, UnavailableAlertAnalysisAgent)
    assert isinstance(composition.reasoning_executor._agent, UnavailableObservationReasoningAgent)
    assert isinstance(composition.report_executor._agent, UnavailableReportGenerationAgent)
    assert isinstance(composition.metric_adapter._pipeline._agent, UnavailableMetricsAnalysisAgent)
    assert isinstance(composition.alert_adapter._agent, UnavailableAlertAnalysisAgent)


def test_unavailable_metric_and_alert_ports_follow_existing_safe_failure_paths() -> None:
    """Unavailable ports expose neither credentials nor provider diagnostics."""
    metric = asyncio.run(UnavailableMetricsAnalysisAgent().complete(None))
    assert isinstance(metric, MetricAgentOperationalFailure)

    with pytest.raises(RuntimeError, match="model access unavailable"):
        asyncio.run(UnavailableAlertAnalysisAgent().complete(None, None))


def test_empty_knowledge_retriever_returns_a_valid_empty_tuple_without_calls() -> None:
    """The production knowledge fallback has no hidden source or fabricated reference."""
    request = KnowledgeRetrievalRequest(query="meaning", finding_ids=("finding-1",))

    assert asyncio.run(EmptyKnowledgeRetriever().retrieve(request)) == ()


def test_configured_composition_uses_real_metric_and_alert_adapters() -> None:
    """A configured deployment composes PydanticAI behind framework-neutral ports."""
    composition = build_production_execution_composition(
        settings=Settings(openrouter_api_key="composition-test-secret"),
        session_factory=async_sessionmaker(),
    )

    assert isinstance(composition.metric_agent, PydanticAIMetricsAnalysisAgent)
    assert isinstance(composition.alert_agent, PydanticAIAlertAnalysisAgent)


def test_unavailable_alert_port_has_no_completion_or_configuration_payload() -> None:
    """The unavailable Alert port cannot fabricate a valid analytical completion."""
    with pytest.raises(RuntimeError):
        asyncio.run(UnavailableAlertAnalysisAgent().complete(None, None))
