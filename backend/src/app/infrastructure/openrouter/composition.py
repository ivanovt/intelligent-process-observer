"""Compose private OpenRouter-backed Observation agent infrastructure."""

# ruff: noqa: E501
from __future__ import annotations

from app.core.diagnostics import OperationalEventEmitter
from app.core.settings import Settings
from app.infrastructure.agents.pydantic_ai_alerts import PydanticAIAlertAnalysisAgent
from app.infrastructure.agents.pydantic_ai_knowledge_scope import (
    PydanticAIKnowledgeScopeSuggestionAgent,
)
from app.infrastructure.agents.pydantic_ai_metrics import PydanticAIMetricsAnalysisAgent
from app.infrastructure.agents.pydantic_ai_reasoning import PydanticAIObservationReasoningAgent
from app.infrastructure.agents.pydantic_ai_reporting import PydanticAIReportGenerationAgent
from app.infrastructure.agents.tracing import AgentTraceRecorder


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


def build_metric_model(settings: Settings):
    """Return the configured OpenRouter model for Metric analysis."""
    return _build_model(settings, settings.metric_analysis_model)


def build_alert_model(settings: Settings):
    """Return the configured OpenRouter model for Alert analysis."""
    return _build_model(settings, settings.alert_analysis_model)


def _build_model(settings: Settings, model_name: str):
    """Compose one private native model without exposing credential material."""
    if (
        settings.openrouter_api_key is None
        or not settings.openrouter_api_key.get_secret_value().strip()
    ):
        raise ValueError("OpenRouter credential is required for model composition")
    from pydantic_ai.models.openrouter import OpenRouterModel
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    provider = OpenRouterProvider(api_key=settings.openrouter_api_key.get_secret_value())
    policy = {"allow_fallbacks": settings.openrouter_allow_fallbacks}
    if settings.openrouter_provider_order:
        policy["order"] = settings.openrouter_provider_order
    return OpenRouterModel(
        model_name,
        provider=provider,
        settings={"extra_body": {"provider": policy}},
    )


def build_metric_agent(
    settings: Settings,
    *,
    trace_recorder: AgentTraceRecorder | None = None,
    emitter: OperationalEventEmitter | None = None,
) -> PydanticAIMetricsAnalysisAgent:
    """Build the configured production adapter for Metric analysis only."""
    return PydanticAIMetricsAnalysisAgent(
        build_metric_model(settings),
        timeout_seconds=settings.metric_analysis_request_timeout_seconds,
        max_output_tokens=settings.metric_analysis_max_output_tokens,
        model_name=settings.metric_analysis_model,
        trace_recorder=trace_recorder,
        emitter=emitter,
    )


def build_alert_agent(
    settings: Settings,
    *,
    trace_recorder: AgentTraceRecorder | None = None,
    emitter: OperationalEventEmitter | None = None,
) -> PydanticAIAlertAnalysisAgent:
    """Build the configured production adapter for Alert analysis only."""
    return PydanticAIAlertAnalysisAgent(
        build_alert_model(settings),
        timeout_seconds=settings.alert_analysis_request_timeout_seconds,
        max_output_tokens=settings.alert_analysis_max_output_tokens,
        model_name=settings.alert_analysis_model,
        trace_recorder=trace_recorder,
        emitter=emitter,
    )


def build_reasoning_agent(
    settings: Settings,
    *,
    trace_recorder: AgentTraceRecorder | None = None,
    emitter: OperationalEventEmitter | None = None,
) -> PydanticAIObservationReasoningAgent:
    """Build the configured production adapter for all Observation Reasoning phases."""
    return PydanticAIObservationReasoningAgent(
        build_reasoning_model(settings),
        timeout_seconds=settings.openrouter_request_timeout_seconds,
        max_output_tokens=settings.observation_reasoning_max_output_tokens,
        model_name=settings.observation_reasoning_model,
        trace_recorder=trace_recorder,
        emitter=emitter,
    )


def build_report_model(settings: Settings):
    """Return the configured OpenRouter model for report presentation."""
    if (
        settings.openrouter_api_key is None
        or not settings.openrouter_api_key.get_secret_value().strip()
    ):
        raise ValueError("OpenRouter credential is required for report model composition")
    from pydantic_ai.models.openrouter import OpenRouterModel
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    provider = OpenRouterProvider(api_key=settings.openrouter_api_key.get_secret_value())
    provider.client.max_retries = 0
    policy = {"allow_fallbacks": settings.openrouter_allow_fallbacks}
    if settings.openrouter_provider_order:
        policy["order"] = settings.openrouter_provider_order
    return OpenRouterModel(
        settings.observation_report_model,
        provider=provider,
        settings={"extra_body": {"provider": policy}},
    )


def build_report_agent(
    settings: Settings,
    *,
    trace_recorder: AgentTraceRecorder | None = None,
    emitter: OperationalEventEmitter | None = None,
) -> PydanticAIReportGenerationAgent:
    """Build the configured production adapter for report presentation only."""
    return PydanticAIReportGenerationAgent(
        build_report_model(settings),
        timeout_seconds=settings.openrouter_request_timeout_seconds,
        max_output_tokens=settings.observation_report_max_output_tokens,
        model_name=settings.observation_report_model,
        trace_recorder=trace_recorder,
        emitter=emitter,
    )


def build_knowledge_scope_suggestion_model(settings: Settings):
    """Return the configured OpenRouter model for advisory scope suggestions."""
    if (
        settings.openrouter_api_key is None
        or not settings.openrouter_api_key.get_secret_value().strip()
    ):
        raise ValueError("OpenRouter credential is required for scope suggestion model composition")
    from pydantic_ai.models.openrouter import OpenRouterModel
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    provider = OpenRouterProvider(api_key=settings.openrouter_api_key.get_secret_value())
    provider.client.max_retries = 0
    policy = {"allow_fallbacks": settings.openrouter_allow_fallbacks}
    if settings.openrouter_provider_order:
        policy["order"] = settings.openrouter_provider_order
    return OpenRouterModel(
        settings.knowledge_scope_suggestion_model,
        provider=provider,
        settings={"extra_body": {"provider": policy}},
    )


def build_knowledge_scope_suggestion_agent(
    settings: Settings,
) -> PydanticAIKnowledgeScopeSuggestionAgent:
    """Build the configured production adapter for advisory scope suggestions only."""
    return PydanticAIKnowledgeScopeSuggestionAgent(
        build_knowledge_scope_suggestion_model(settings),
        timeout_seconds=settings.openrouter_request_timeout_seconds,
        max_output_tokens=settings.observation_reasoning_max_output_tokens,
    )
