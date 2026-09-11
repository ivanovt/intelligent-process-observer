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
    AlertTerminalOutcome,
)
from app.alerts.pipeline import AlertAnalysisPipeline
from app.alerts.ports import AlertAnalysisAgent, AlertProvider
from app.core.diagnostics import DiagnosticEvent, OperationalEventEmitter
from app.execution.contracts import (
    AlertLensSnapshot,
    CollectedLensOutcome,
    ExecutionPolicy,
    ExecutionReason,
    LensExecutionAssignment,
    MetricLensSnapshot,
)
from app.infrastructure.persistence.alert_runtime import persist_alert_terminal
from app.infrastructure.persistence.models import (
    LensAnalysisResultModel,
    LensRunModel,
    ObservationRunModel,
)
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensResultIdentity,
    LensRunStatus,
    LensType,
    StructuredReason,
)
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricHistoryPolicy,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricMandatoryAnalysisFailure,
    MetricProviderScope,
)
from app.metrics.pipeline import MetricAnalysisPipeline, MetricPreTransactionAnalysis
from app.metrics.result_builder import MetricResultBuilder


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
        repository: RuntimePersistenceRepository,
        emitter: OperationalEventEmitter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._pipeline = pipeline
        self._repository = repository
        self._emitter = emitter or OperationalEventEmitter()

    async def execute(
        self, assignment: LensExecutionAssignment, policy: ExecutionPolicy
    ) -> CollectedLensOutcome:
        """Analyze under the Lens deadline, then terminalize Metric work outside it."""

        context = metric_execution_context(assignment)
        deadline = asyncio.timeout(policy.lens_deadline_seconds)
        try:
            async with deadline:
                analysis = await self._pipeline.analyze(context)
        except TimeoutError as error:
            self._emit_failure(assignment, "metric_lens_deadline_exceeded", "timeout", error)
            return await self._persist_wrapper_failure(
                assignment, context, "timeout" if deadline.expired() else "analysis_failed"
            )
        except Exception as error:
            self._emit_failure(assignment, "metric_lens_analysis_failed", "analysis_failed", error)
            return await self._persist_wrapper_failure(assignment, context, "analysis_failed")
        try:
            _validate_metric_analysis(analysis, context)
        except Exception as error:
            self._emit_failure(assignment, "metric_lens_result_invalid", "identity_mismatch", error)
            return await self._persist_wrapper_failure(assignment, context, "identity_mismatch")
        async with self._session_factory.begin() as session:
            lens_run = await _load_assigned_running_lens(session, assignment)
            persisted = await self._pipeline.persist_terminal(
                cast(object, session), lens_run, analysis
            )
            return _collected_outcome(
                assignment, lens_run, _persisted_artifact(persisted, assignment)
            )

    def _emit_failure(
        self,
        assignment: LensExecutionAssignment,
        event: str,
        category: str,
        error: BaseException,
    ) -> None:
        """Log a safe Metric adapter normalization without exposing Lens scope."""
        self._emitter.emit(
            DiagnosticEvent(
                event=event,
                category=category,
                observation_run_id=assignment.observation_run_id,
                lens_run_id=assignment.lens_run_id,
                lens_id=assignment.lens.lens_id,
                component="metric_execution_adapter",
                stage="lens_execution",
            ),
            error=error,
        )

    async def _persist_wrapper_failure(
        self,
        assignment: LensExecutionAssignment,
        context: MetricLensExecutionContext,
        code: str,
    ) -> CollectedLensOutcome:
        """Persist one adapter-owned Metric failure without exposing diagnostics."""

        _, artifact = MetricResultBuilder().failed(
            context, MetricMandatoryAnalysisFailure(diagnostic="adapter normalization")
        )
        async with self._session_factory.begin() as session:
            lens_run = await _load_assigned_running_lens(session, assignment)
            await self._repository.advance_lens_run(
                cast(object, session),
                lens_run,
                LensRunStatus.FAILED,
                reason=StructuredReason(code=code, component="metric"),
            )
            persisted = await self._repository.persist_lens_analysis_result(
                cast(object, session), lens_run, artifact
            )
            return _collected_outcome(
                assignment, lens_run, _persisted_artifact(persisted, assignment)
            )


class AlertLensExecutionAdapter:
    """Run the existing Alert pipeline and persist its terminal outcome atomically."""

    def __init__(
        self,
        *,
        session_factory: TerminalSessionFactory,
        repository: RuntimePersistenceRepository,
        provider_resolver: AlertProviderResolver,
        agent: AlertAnalysisAgent,
        emitter: OperationalEventEmitter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository = repository
        self._provider_resolver = provider_resolver
        self._agent = agent
        self._emitter = emitter or OperationalEventEmitter()

    async def execute(
        self, assignment: LensExecutionAssignment, policy: ExecutionPolicy
    ) -> CollectedLensOutcome:
        """Analyze under the Lens deadline, then terminalize Alert work outside it."""

        context = alert_execution_context(assignment)
        deadline = asyncio.timeout(policy.lens_deadline_seconds)
        try:
            async with deadline:
                provider = self._provider_resolver.resolve(context.provider_scope)
                pipeline = AlertAnalysisPipeline(provider=provider, agent=self._agent)
                outcome = await pipeline.analyze(context)
        except TimeoutError as error:
            self._emit_failure(assignment, "alert_lens_deadline_exceeded", "timeout", error)
            return await self._persist_wrapper_failure(
                assignment, "timeout" if deadline.expired() else "analysis_failed"
            )
        except Exception as error:
            self._emit_failure(assignment, "alert_lens_analysis_failed", "analysis_failed", error)
            return await self._persist_wrapper_failure(assignment, "analysis_failed")
        try:
            _validate_alert_outcome(outcome, context)
        except Exception as error:
            self._emit_failure(assignment, "alert_lens_result_invalid", "identity_mismatch", error)
            return await self._persist_wrapper_failure(assignment, "identity_mismatch")
        async with self._session_factory.begin() as session:
            lens_run = await _load_assigned_running_lens(session, assignment)
            persisted = await persist_alert_terminal(
                cast(object, session), lens_run, outcome, self._repository
            )
            return _collected_outcome(
                assignment,
                lens_run,
                _persisted_artifact(persisted, assignment) if persisted is not None else None,
            )

    def _emit_failure(
        self,
        assignment: LensExecutionAssignment,
        event: str,
        category: str,
        error: BaseException,
    ) -> None:
        """Log a safe Alert adapter normalization without exposing selector content."""
        self._emitter.emit(
            DiagnosticEvent(
                event=event,
                category=category,
                observation_run_id=assignment.observation_run_id,
                lens_run_id=assignment.lens_run_id,
                lens_id=assignment.lens.lens_id,
                component="alert_execution_adapter",
                stage="lens_execution",
            ),
            error=error,
        )

    async def _persist_wrapper_failure(
        self, assignment: LensExecutionAssignment, code: str
    ) -> CollectedLensOutcome:
        """Persist one artifact-free adapter-owned Alert failure."""

        outcome = AlertTerminalOutcome(
            status=LensRunStatus.FAILED,
            reason=StructuredReason(code=code, component="alert"),
        )
        async with self._session_factory.begin() as session:
            lens_run = await _load_assigned_running_lens(session, assignment)
            persisted = await persist_alert_terminal(
                cast(object, session), lens_run, outcome, self._repository
            )
            return _collected_outcome(
                assignment,
                lens_run,
                _persisted_artifact(persisted, assignment) if persisted is not None else None,
            )


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


def _validate_metric_analysis(analysis: object, context: MetricLensExecutionContext) -> None:
    if not isinstance(analysis, MetricPreTransactionAnalysis):
        raise ValueError("Metric pipeline returned an invalid pre-transaction analysis")
    if analysis.context != context:
        raise ValueError("Metric pipeline analysis identity differs from its assignment")
    artifact = analysis.terminal_result
    if not isinstance(artifact, LensAnalysisResultInput):
        raise ValueError("Metric pipeline analysis returned an invalid terminal artifact")
    LensAnalysisResultInput.model_validate(artifact.model_dump())
    if (
        artifact.result_type is not LensType.METRIC
        or artifact.identity.observation_id != context.identity.observation_id
        or artifact.identity.observation_run_id != context.identity.observation_run_id
        or artifact.identity.lens_id != context.identity.lens_id
        or artifact.identity.lens_run_id != context.identity.lens_run_id
        or artifact.identity.metric_ref != context.identity.metric_ref
        or artifact.identity.unit != context.identity.unit
    ):
        raise ValueError("Metric pipeline artifact identity differs from its assignment")
    if analysis.failure is not None:
        if artifact.status is not LensRunStatus.FAILED:
            raise ValueError("Failed Metric analysis requires a failed terminal artifact")
    elif artifact.status not in {LensRunStatus.COMPLETED, LensRunStatus.PARTIAL}:
        raise ValueError("Successful Metric analysis requires a usable terminal artifact")


def _validate_alert_outcome(outcome: object, context: AlertLensExecutionContext) -> None:
    if not isinstance(outcome, AlertTerminalOutcome):
        raise ValueError("Alert pipeline returned an invalid terminal outcome")
    artifact = getattr(outcome, "artifact", None)
    if artifact is None:
        return
    identity = artifact.identity
    expected = context.identity
    if (
        artifact.result_type is not LensType.ALERT
        or artifact.status is not outcome.status
        or identity.observation_id != expected.observation_id
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
    assignment: LensExecutionAssignment,
    lens_run: LensRunModel,
    artifact: LensAnalysisResultInput | None,
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
    return CollectedLensOutcome(
        assignment=assignment, status=status.value, artifact=artifact, reason=reason
    )


def _persisted_artifact(
    persisted: object, assignment: LensExecutionAssignment
) -> LensAnalysisResultInput:
    """Rebuild and validate the exact envelope just accepted by persistence."""

    if not isinstance(persisted, LensAnalysisResultModel):
        raise ValueError("terminal persistence did not return a Lens analysis result")
    if persisted.lens_run_id != assignment.lens_run_id:
        raise ValueError("terminal persistence returned an artifact for another LensRun")
    payload = persisted.payload
    if not isinstance(payload, dict):
        raise ValueError("persisted Lens analysis result payload must be an object")
    identity = payload.get("identity")
    provenance = payload.get("provenance")
    if not isinstance(identity, dict) or not isinstance(provenance, dict):
        raise ValueError("persisted Lens analysis result lacks identity or provenance")
    return LensAnalysisResultInput(
        result_type=LensType(persisted.result_type),
        status=LensRunStatus(persisted.status),
        schema_version=persisted.schema_version,
        identity=LensResultIdentity.model_validate(identity),
        provenance=provenance,
        payload=payload,
    )
