"""Assemble the production Observation execution graph at application lifespan."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings
from app.execution import AlertLensExecutionAdapter, MetricLensExecutionAdapter
from app.execution.orchestrator import ObservationExecutionOrchestrator
from app.infrastructure.agents.unavailable import (
    UnavailableAlertAnalysisAgent,
    UnavailableMetricsAnalysisAgent,
    UnavailableObservationReasoningAgent,
    UnavailableReportGenerationAgent,
)
from app.infrastructure.jira import JiraAlertProviderResolver
from app.infrastructure.openrouter.composition import (
    build_alert_agent,
    build_metric_agent,
    build_reasoning_agent,
    build_report_agent,
)
from app.infrastructure.persistence.repository import (
    ObservationRepository,
    RuntimePersistenceRepository,
)
from app.infrastructure.prometheus.composition import PrometheusMetricSeriesProvider
from app.knowledge.empty import EmptyKnowledgeRetriever
from app.metrics.pipeline import MetricAnalysisPipeline
from app.reasoning.executor import ObservationReasoningExecutor
from app.relationships.evaluator import RelationshipEvaluator
from app.reporting.executor import ReportGenerationExecutor


@dataclass(frozen=True, slots=True)
class ProductionExecutionComposition:
    """Lifespan-owned production components for one single-process execution host."""

    orchestrator: ObservationExecutionOrchestrator
    metric_adapter: MetricLensExecutionAdapter
    alert_adapter: AlertLensExecutionAdapter
    metric_agent: object
    alert_agent: object
    reasoning_executor: ObservationReasoningExecutor
    report_executor: ReportGenerationExecutor
    knowledge_retriever: EmptyKnowledgeRetriever


def build_production_execution_composition(
    *, settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> ProductionExecutionComposition:
    """Create the complete server-owned graph without leaking infrastructure into ports."""
    runtime_repository = RuntimePersistenceRepository()
    metric_agent, alert_agent, reasoning_agent, report_agent = _production_agents(settings)
    metric_provider = PrometheusMetricSeriesProvider(settings.prometheus_sources)
    alert_provider_resolver = JiraAlertProviderResolver(settings.jira_alert_provider_raw)
    metric_adapter = MetricLensExecutionAdapter(
        session_factory=session_factory,
        pipeline=MetricAnalysisPipeline(
            provider=metric_provider,
            agent=metric_agent,
            history_reader=runtime_repository,
            repository=runtime_repository,
        ),
        repository=runtime_repository,
    )
    alert_adapter = AlertLensExecutionAdapter(
        session_factory=session_factory,
        repository=runtime_repository,
        provider_resolver=alert_provider_resolver,
        agent=alert_agent,
    )
    knowledge_retriever = EmptyKnowledgeRetriever()
    reasoning_executor = ObservationReasoningExecutor(reasoning_agent, knowledge_retriever)
    report_executor = ReportGenerationExecutor(report_agent)
    orchestrator = ObservationExecutionOrchestrator(
        session_factory=session_factory,
        definition_loader=ObservationRepository(),
        runtime_repository=runtime_repository,
        metric_adapter=metric_adapter,
        alert_adapter=alert_adapter,
        relationship_evaluator=RelationshipEvaluator(),
        reasoning_executor=reasoning_executor,
        report_executor=report_executor,
    )
    return ProductionExecutionComposition(
        orchestrator=orchestrator,
        metric_adapter=metric_adapter,
        alert_adapter=alert_adapter,
        metric_agent=metric_agent,
        alert_agent=alert_agent,
        reasoning_executor=reasoning_executor,
        report_executor=report_executor,
        knowledge_retriever=knowledge_retriever,
    )


def _production_agents(settings: Settings) -> tuple[object, object, object, object]:
    """Use real adapters only with a non-blank OpenRouter credential."""
    if (
        settings.openrouter_api_key is None
        or not settings.openrouter_api_key.get_secret_value().strip()
    ):
        return (
            UnavailableMetricsAnalysisAgent(),
            UnavailableAlertAnalysisAgent(),
            UnavailableObservationReasoningAgent(),
            UnavailableReportGenerationAgent(),
        )
    return (
        build_metric_agent(settings),
        build_alert_agent(settings),
        build_reasoning_agent(settings),
        build_report_agent(settings),
    )
