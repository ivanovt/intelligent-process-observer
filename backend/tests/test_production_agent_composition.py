"""Focused production composition tests for Metric and Alert model boundaries."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.diagnostics import OperationalEventEmitter
from app.core.settings import Settings
from app.infrastructure.agents.pydantic_ai_alerts import PydanticAIAlertAnalysisAgent
from app.infrastructure.agents.pydantic_ai_metrics import PydanticAIMetricsAnalysisAgent
from app.infrastructure.agents.tracing import FileAgentTraceRecorder, NoOpAgentTraceRecorder
from app.infrastructure.agents.unavailable import (
    UnavailableAlertAnalysisAgent,
    UnavailableMetricsAnalysisAgent,
    UnavailableObservationReasoningAgent,
    UnavailableReportGenerationAgent,
)
from app.infrastructure.execution.composition import build_production_execution_composition
from app.infrastructure.knowledge.retrieval import CuratedKnowledgeRetriever
from app.infrastructure.openrouter.composition import (
    build_alert_agent,
    build_alert_model,
    build_metric_agent,
    build_metric_model,
)
from app.knowledge.contracts import KnowledgeRetrievalRequest
from app.knowledge.empty import EmptyKnowledgeRetriever
from app.knowledge.management_contracts import KnowledgeScope, KnowledgeServiceScope
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
        settings=Settings(openrouter_api_key=None), session_factory=async_sessionmaker()
    )

    assert isinstance(composition.metric_agent, UnavailableMetricsAnalysisAgent)
    assert isinstance(composition.alert_agent, UnavailableAlertAnalysisAgent)
    assert isinstance(composition.reasoning_executor._agent, UnavailableObservationReasoningAgent)
    assert isinstance(composition.report_executor._agent, UnavailableReportGenerationAgent)
    assert isinstance(composition.metric_adapter._pipeline._agent, UnavailableMetricsAnalysisAgent)
    assert isinstance(composition.alert_adapter._agent, UnavailableAlertAnalysisAgent)


def test_composition_selects_trace_recorder_from_development_only_setting() -> None:
    """The fixed trace root is selected without creating it in disabled mode."""
    emitter = OperationalEventEmitter()
    disabled = build_production_execution_composition(
        settings=Settings(openrouter_api_key=None),
        session_factory=async_sessionmaker(),
        emitter=emitter,
    )
    enabled_settings = Settings(
        app_env="development", agent_trace_enabled=True, openrouter_api_key=None
    )
    enabled = build_production_execution_composition(
        settings=enabled_settings,
        session_factory=async_sessionmaker(),
        emitter=emitter,
    )

    assert isinstance(disabled.trace_recorder, NoOpAgentTraceRecorder)
    assert disabled.reasoning_executor._trace_recorder is disabled.trace_recorder
    assert disabled.reasoning_executor._emitter is emitter
    assert disabled.report_executor._trace_recorder is disabled.trace_recorder
    assert disabled.report_executor._emitter is emitter
    assert isinstance(enabled.trace_recorder, FileAgentTraceRecorder)
    assert enabled.reasoning_executor._trace_recorder is enabled.trace_recorder
    assert enabled.reasoning_executor._emitter is emitter
    assert enabled.report_executor._trace_recorder is enabled.trace_recorder
    assert enabled.report_executor._emitter is emitter
    assert enabled.trace_recorder.root == enabled_settings.agent_trace_root


def test_missing_openrouter_configuration_emits_safe_operational_metadata() -> None:
    """Unavailable agent ports are visible without disclosing configuration values."""
    messages: list[str] = []
    logger = logging.getLogger("test.production-composition.operational")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    build_production_execution_composition(
        settings=Settings(openrouter_api_key=None),
        session_factory=async_sessionmaker(),
        emitter=OperationalEventEmitter(logger=logger),
    )

    payloads = [json.loads(message) for message in messages]
    event = next(item for item in payloads if item["event"] == "agent_configuration_unavailable")
    assert event == {
        "category": "agent_configuration_missing",
        "component": "production_composition",
        "event": "agent_configuration_unavailable",
        "level": "warning",
        "timestamp": event["timestamp"],
    }


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


def test_composition_creates_an_isolated_curated_retriever_for_each_run_scope() -> None:
    """A scope chooses retrieval candidates per run without mutating the shared executor."""
    emitter = OperationalEventEmitter()
    composition = build_production_execution_composition(
        settings=Settings(openrouter_api_key="composition-test-secret", agent_trace_enabled=False),
        session_factory=async_sessionmaker(),
        emitter=emitter,
    )
    scope = KnowledgeScope(
        services=(KnowledgeServiceScope(service_id="mprm-server", service_version="2.x"),)
    )

    run_id = UUID("00000000-0000-0000-0000-000000000001")
    first = composition.knowledge_retriever_factory(scope, run_id)
    second = composition.knowledge_retriever_factory(None, None)

    assert isinstance(first, CuratedKnowledgeRetriever)
    assert isinstance(second, CuratedKnowledgeRetriever)
    assert first is not second
    assert first._scope == scope
    assert second._scope is None
    assert first._observation_run_id == run_id
    assert second._observation_run_id is None
    assert first._emitter is emitter
    assert second._emitter is emitter


def test_missing_embedding_configuration_uses_empty_retriever_factory() -> None:
    """Unavailable knowledge composition is an empty fallback before any run begins."""
    composition = build_production_execution_composition(
        settings=Settings(openrouter_api_key=None, agent_trace_enabled=False),
        session_factory=async_sessionmaker(),
    )

    assert isinstance(
        composition.knowledge_retriever_factory(
            KnowledgeScope(services=(KnowledgeServiceScope(service_id="mprm-server"),)), None
        ),
        EmptyKnowledgeRetriever,
    )


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


class _CollectingHandler(logging.Handler):
    """Collect operational messages without depending on process-global logging state."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__()
        self._messages = messages

    def emit(self, record: logging.LogRecord) -> None:
        """Store the rendered message for deterministic assertions."""
        self._messages.append(record.getMessage())
