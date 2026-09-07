"""Type-specific composition adapters for admitted Observation LensRuns."""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Protocol, cast

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertProviderScope,
)
from app.alerts.pipeline import AlertAnalysisPipeline
from app.alerts.ports import AlertAnalysisAgent, AlertProvider
from app.execution.contracts import (
    AlertLensSnapshot,
    CollectedLensOutcome,
    ExecutionPolicy,
    ExecutionReason,
    LensExecutionAssignment,
    MetricLensSnapshot,
)
from app.infrastructure.persistence.alert_runtime import persist_alert_terminal
from app.infrastructure.persistence.models import LensRunModel, ObservationRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import LensRunStatus
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricHistoryPolicy,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricProviderScope,
)
from app.metrics.pipeline import MetricAnalysisPipeline, MetricPreTransactionAnalysis


class TerminalSessionFactory(Protocol):
    """Open one short caller-owned transaction for Lens terminalization."""

    def begin(self) -> AbstractAsyncContextManager[object]:
        """Return the context manager that commits or rolls back one transaction."""


class AlertProviderResolver(Protocol):
    """Resolve the configured Alert provider at the type-specific boundary."""

    def resolve(self, scope: AlertProviderScope) -> AlertProvider:
        """Return the provider that serves the supplied frozen Alert scope."""


class MetricLensExecutionAdapter:
    """Run the existing Metric pipeline around its required History transaction boundary."""

    def __init__(
        self,
        *,
        session_factory: TerminalSessionFactory,
        pipeline: MetricAnalysisPipeline,
    ) -> None:
        self._session_factory = session_factory
        self._pipeline = pipeline

    async def execute(
        self, assignment: LensExecutionAssignment, policy: ExecutionPolicy
    ) -> CollectedLensOutcome:
        """Analyze under the Lens deadline, then terminalize Metric work outside it."""

        context = metric_execution_context(assignment)
        async with asyncio.timeout(policy.lens_deadline_seconds):
            analysis = await self._pipeline.analyze(context)
        _validate_metric_analysis(analysis, context)
        async with self._session_factory.begin() as session:
            lens_run = await _load_assigned_running_lens(session, assignment)
            await self._pipeline.persist_terminal(cast(object, session), lens_run, analysis)
            return _collected_outcome(assignment, lens_run)


class AlertLensExecutionAdapter:
    """Run the existing Alert pipeline and persist its terminal outcome atomically."""

    def __init__(
        self,
        *,
        session_factory: TerminalSessionFactory,
        repository: RuntimePersistenceRepository,
        provider_resolver: AlertProviderResolver,
        agent: AlertAnalysisAgent,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository
        self._provider_resolver = provider_resolver
        self._agent = agent

    async def execute(
        self, assignment: LensExecutionAssignment, policy: ExecutionPolicy
    ) -> CollectedLensOutcome:
        """Analyze under the Lens deadline, then terminalize Alert work outside it."""

        context = alert_execution_context(assignment)
        provider = self._provider_resolver.resolve(context.provider_scope)
        pipeline = AlertAnalysisPipeline(provider=provider, agent=self._agent)
        async with asyncio.timeout(policy.lens_deadline_seconds):
            outcome = await pipeline.analyze(context)
        _validate_alert_outcome(outcome, context)
        async with self._session_factory.begin() as session:
            lens_run = await _load_assigned_running_lens(session, assignment)
            await persist_alert_terminal(cast(object, session), lens_run, outcome, self._repository)
            return _collected_outcome(assignment, lens_run)


def metric_execution_context(assignment: LensExecutionAssignment) -> MetricLensExecutionContext:
    """Project one frozen Metric assignment into the existing Metric pipeline context."""

    if not isinstance(assignment.lens, MetricLensSnapshot):
        raise ValueError("Metric adapter requires a Metric Lens assignment")
    lens = assignment.lens
    return MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=assignment.observation_id,
            observation_run_id=assignment.observation_run_id,
            lens_id=lens.lens_id,
            lens_run_id=assignment.lens_run_id,
            metric_ref=lens.metric_id,
            unit=lens.unit,
        ),
        provider_scope=MetricProviderScope(
            adapter_type=lens.adapter_type, source_id=lens.source_id, query=lens.query
        ),
        analysis_window=MetricAnalysisWindow(
            **{"from": assignment.analysis_window.from_, "to": assignment.analysis_window.to}
        ),
        analysis_objectives=lens.analysis_objectives,
        reference_periods=lens.reference_periods,
        history_policy=MetricHistoryPolicy(),
    )


def alert_execution_context(assignment: LensExecutionAssignment) -> AlertLensExecutionContext:
    """Project one frozen Alert assignment into the existing Alert pipeline context."""

    if not isinstance(assignment.lens, AlertLensSnapshot):
        raise ValueError("Alert adapter requires an Alert Lens assignment")
    lens = assignment.lens
    return AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=assignment.observation_id,
            observation_run_id=assignment.observation_run_id,
            lens_id=lens.lens_id,
            lens_run_id=assignment.lens_run_id,
        ),
        provider_scope=AlertProviderScope(source=lens.source, query=lens.selector_query),
        analysis_window=AlertAnalysisWindow(
            **{"from": assignment.analysis_window.from_, "to": assignment.analysis_window.to}
        ),
        lens_name=lens.name,
        lens_description=lens.description,
        analysis_objectives=lens.analysis_objectives,
        reference_periods=lens.reference_periods,
        lens_run_status="running",
    )


def _validate_metric_analysis(
    analysis: MetricPreTransactionAnalysis, context: MetricLensExecutionContext
) -> None:
    if analysis.context != context:
        raise ValueError("Metric pipeline analysis identity differs from its assignment")


def _validate_alert_outcome(outcome: object, context: AlertLensExecutionContext) -> None:
    artifact = getattr(outcome, "artifact", None)
    if artifact is None:
        return
    identity = artifact.identity
    expected = context.identity
    if (
        identity.observation_id != expected.observation_id
        or identity.observation_run_id != expected.observation_run_id
        or identity.lens_id != expected.lens_id
        or identity.lens_run_id != expected.lens_run_id
    ):
        raise ValueError("Alert pipeline outcome identity differs from its assignment")


async def _load_assigned_running_lens(
    session: object, assignment: LensExecutionAssignment
) -> LensRunModel:
    lens_run = await session.get(LensRunModel, assignment.lens_run_id)
    observation_run = await session.get(ObservationRunModel, assignment.observation_run_id)
    if (
        lens_run is None
        or observation_run is None
        or observation_run.id != assignment.observation_run_id
        or observation_run.observation_id != assignment.observation_id
        or lens_run.observation_run_id != assignment.observation_run_id
        or lens_run.lens_id != assignment.lens.lens_id
        or lens_run.lens_type != assignment.lens.lens_type
        or lens_run.status != LensRunStatus.RUNNING.value
    ):
        raise ValueError("assigned LensRun is not the expected running runtime record")
    return lens_run


def _collected_outcome(
    assignment: LensExecutionAssignment, lens_run: LensRunModel
) -> CollectedLensOutcome:
    status = LensRunStatus(lens_run.status)
    if status not in {LensRunStatus.COMPLETED, LensRunStatus.PARTIAL, LensRunStatus.FAILED}:
        raise ValueError("Lens terminal persistence returned a non-terminal status")
    reason = None
    if lens_run.reason is not None:
        reason = ExecutionReason(
            code=str(lens_run.reason["code"]),
            component=(
                str(lens_run.reason["component"])
                if lens_run.reason.get("component") is not None
                else None
            ),
        )
    return CollectedLensOutcome(assignment=assignment, status=status.value, reason=reason)
