"""Deterministic VS-01 Metric walking-skeleton application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.diagnostics import DiagnosticEvent, OperationalEventEmitter
from app.infrastructure.persistence.models import LensAnalysisResultModel, LensRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensRunStatus,
    StructuredReason,
)
from app.metrics.contracts import (
    MetricAgentCompletion,
    MetricAgentInsufficientRequest,
    MetricAgentOperationalFailure,
    MetricAgentProtocolFailure,
    MetricAgentUsableRequest,
    MetricAnalysisWindow,
    MetricCurrentAcquisitionFailed,
    MetricCurrentEvidence,
    MetricCurrentFailure,
    MetricCurrentSeriesMalformed,
    MetricHistoryCandidates,
    MetricLensExecutionContext,
    MetricMandatoryAnalysisFailure,
    MetricOptionalProjections,
    MetricReferenceComparison,
    MetricReferenceEvidence,
    MetricReferenceUnavailable,
    MetricSemantics,
    MetricSeriesAcquisitionFailure,
    MetricSeriesAcquisitionTimeout,
    MetricSeriesUnavailable,
    MetricToolAttempt,
    PreparedInsufficientSeries,
    PreparedSeries,
    PreparedUsableSeries,
)
from app.metrics.history import analyze_history
from app.metrics.ports import MetricHistoryReader, MetricsAnalysisAgent, MetricSeriesProvider
from app.metrics.preprocessing import MetricSeriesMalformedError, prepare_series
from app.metrics.references import compare_reference, reference_window
from app.metrics.result_builder import MetricResultBuilder
from app.metrics.semantics import semanticize_mandatory
from app.metrics.tools import (
    MetricToolRegistry,
    earliest_optional_tool_failure,
    project_successful_optional_tools,
)

PhaseRecorder = Callable[[str], None]


@dataclass(frozen=True)
class MetricPreTransactionAnalysis:
    context: MetricLensExecutionContext
    prepared: PreparedSeries | None
    semantics: MetricSemantics | None
    dataset_ref: str | None
    insufficient_agent_outcome: MetricAgentCompletion | MetricAgentOperationalFailure | None
    terminal_result: LensAnalysisResultInput
    failure: MetricCurrentFailure | None = None
    reference_diagnostics: tuple[MetricReferenceUnavailable, ...] = ()
    reference_periods: tuple[MetricReferenceComparison, ...] = ()
    reference_evidence: tuple[MetricReferenceEvidence, ...] = ()
    optional_projections: MetricOptionalProjections = MetricOptionalProjections()
    optional_failure_component: str | None = None
    agent_protocol_failure: MetricAgentProtocolFailure | None = None
    tool_ledger: tuple[MetricToolAttempt, ...] = ()


@dataclass(frozen=True)
class PreparedReferenceAnalysis:
    offset: str
    window: MetricAnalysisWindow
    prepared: PreparedUsableSeries
    semantics: MetricSemantics


class MetricAnalysisPipeline:
    """Analyze before the caller-owned transaction, then persist inside it."""

    def __init__(
        self,
        *,
        provider: MetricSeriesProvider,
        agent: MetricsAnalysisAgent,
        history_reader: MetricHistoryReader,
        repository: RuntimePersistenceRepository,
        result_builder: MetricResultBuilder | None = None,
        record_phase: PhaseRecorder | None = None,
        emitter: OperationalEventEmitter | None = None,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        self._provider = provider
        self._agent = agent
        self._history_reader = history_reader
        self._repository = repository
        self._result_builder = result_builder or MetricResultBuilder()
        self._record_phase = record_phase or (lambda _: None)
        self._emitter = emitter or OperationalEventEmitter()
        self._monotonic_clock = monotonic_clock or monotonic

    async def analyze(self, context: MetricLensExecutionContext) -> MetricPreTransactionAnalysis:
        """Perform the stages that must not hold the History/write transaction open."""

        self._record_phase("provider_acquisition")
        acquisition_started = self._monotonic_clock()
        try:
            available = await self._provider.acquire(
                context.provider_scope, context.analysis_window
            )
        except TimeoutError as error:
            self._emit_acquisition_failure(
                context,
                category="acquisition_timeout",
                duration_ms=self._duration_ms(acquisition_started),
                exception_type=type(error).__name__,
            )
            return self._failed_analysis(
                context, MetricCurrentAcquisitionFailed(diagnostic=_diagnostic(error))
            )
        except Exception as error:
            self._emit_acquisition_failure(
                context,
                category="provider_failure",
                duration_ms=self._duration_ms(acquisition_started),
                exception_type=type(error).__name__,
            )
            return self._failed_analysis(
                context, MetricCurrentAcquisitionFailed(diagnostic=_diagnostic(error))
            )
        if isinstance(
            available,
            (
                MetricSeriesUnavailable,
                MetricSeriesAcquisitionFailure,
                MetricSeriesAcquisitionTimeout,
            ),
        ):
            self._emit_acquisition_failure(
                context,
                category=available.diagnostic_category,
                duration_ms=self._duration_ms(acquisition_started),
                attempt_count=available.attempt_count,
                http_status=getattr(available, "http_status", None),
                observed_series_count=getattr(available, "observed_series_count", None),
            )
            return self._failed_analysis(
                context, MetricCurrentAcquisitionFailed(diagnostic=available.diagnostic)
            )
        self._record_phase("current_preparation")
        try:
            prepared = prepare_series(available.samples, context.analysis_window)
        except MetricSeriesMalformedError as error:
            self._emit_failure(context, "metric_schema_rejected", "current_preparation", error)
            return self._failed_analysis(
                context, MetricCurrentSeriesMalformed(diagnostic=_diagnostic(error))
            )
        except Exception as error:
            self._emit_failure(context, "metric_internal_failed", "current_preparation", error)
            return self._failed_analysis(
                context, MetricMandatoryAnalysisFailure(diagnostic=_diagnostic(error))
            )
        if isinstance(prepared, PreparedInsufficientSeries):
            request = MetricAgentInsufficientRequest(
                identity=context.identity,
                analysis_window=context.analysis_window,
                data_quality="insufficient",
            )
            self._record_phase("agent_execution")
            try:
                outcome = await self._agent.complete(request)
                completion = MetricAgentCompletion.model_validate(outcome)
            except Exception as error:
                self._emit_failure(context, "metric_internal_failed", "agent_execution", error)
                completion = MetricAgentOperationalFailure()
            try:
                _, terminal_result = self._result_builder.completed_insufficient(context)
            except Exception as error:
                self._emit_failure(context, "metric_internal_failed", "result_builder", error)
                return self._failed_analysis(
                    context, MetricMandatoryAnalysisFailure(diagnostic=_diagnostic(error))
                )
            return MetricPreTransactionAnalysis(
                context=context,
                prepared=prepared,
                semantics=None,
                dataset_ref=None,
                insufficient_agent_outcome=completion,
                terminal_result=terminal_result,
            )

        usable_prepared: PreparedUsableSeries = prepared
        self._record_phase("mandatory_semanticization")
        try:
            semantics = semanticize_mandatory(usable_prepared, context.analysis_window)
        except Exception as error:
            self._emit_failure(
                context, "metric_internal_failed", "mandatory_semanticization", error
            )
            return self._failed_analysis(
                context, MetricMandatoryAnalysisFailure(diagnostic=_diagnostic(error))
            )
        prepared_references, reference_diagnostics = await self._prepare_references(context)
        dataset_ref = uuid4().hex
        registry = MetricToolRegistry(dataset_ref, usable_prepared)
        request = MetricAgentUsableRequest(
            identity=context.identity,
            analysis_window=context.analysis_window,
            analysis_objectives=context.analysis_objectives,
            data_quality=usable_prepared.data_quality,
            evidence=usable_prepared.evidence,
            semantics=semantics,
            allowed_tools=registry.descriptors,
            dataset_ref=dataset_ref,
        )
        self._record_phase("agent_execution")
        try:
            completion = MetricAgentCompletion.model_validate(
                await self._agent.complete(request, registry)
            )
        except Exception as error:
            self._emit_failure(context, "metric_internal_failed", "agent_execution", error)
            completion = MetricAgentOperationalFailure()
        tool_ledger = registry.ledger
        optional_projections = project_successful_optional_tools(tool_ledger)
        agent_protocol_failure = registry.protocol_failure
        optional_failure_component = (
            "metrics_agent"
            if agent_protocol_failure is not None
            or isinstance(completion, MetricAgentOperationalFailure)
            else earliest_optional_tool_failure(tool_ledger)
        )
        comparisons, reference_evidence, comparison_diagnostics = self._compare_references(
            current=usable_prepared,
            current_semantics=semantics,
            references=prepared_references,
        )
        reference_diagnostics = (*reference_diagnostics, *comparison_diagnostics)
        try:
            if reference_diagnostics:
                _, terminal_result = self._result_builder.partial_reference_unavailable(
                    context,
                    usable_prepared,
                    semantics,
                    comparisons,
                    reference_evidence,
                    optional=optional_projections,
                )
            elif optional_failure_component is not None:
                _, terminal_result = self._result_builder.partial_optional_analysis_failed(
                    context,
                    usable_prepared,
                    semantics,
                    optional_failure_component,
                    optional_projections,
                    comparisons,
                    reference_evidence,
                )
            else:
                _, terminal_result = self._result_builder.completed_sufficient(
                    context,
                    usable_prepared,
                    semantics,
                    comparisons,
                    reference_evidence,
                    optional=optional_projections,
                )
        except Exception as error:
            self._emit_failure(context, "metric_internal_failed", "result_builder", error)
            return self._failed_analysis(
                context, MetricMandatoryAnalysisFailure(diagnostic=_diagnostic(error))
            )
        return MetricPreTransactionAnalysis(
            context=context,
            prepared=usable_prepared,
            semantics=semantics,
            dataset_ref=dataset_ref,
            insufficient_agent_outcome=None,
            terminal_result=terminal_result,
            reference_diagnostics=reference_diagnostics,
            reference_periods=comparisons,
            reference_evidence=reference_evidence,
            optional_projections=optional_projections,
            optional_failure_component=optional_failure_component,
            agent_protocol_failure=agent_protocol_failure,
            tool_ledger=tool_ledger,
        )

    async def _prepare_references(
        self,
        context: MetricLensExecutionContext,
    ) -> tuple[
        tuple[PreparedReferenceAnalysis, ...],
        tuple[MetricReferenceUnavailable, ...],
    ]:
        prepared_references: list[PreparedReferenceAnalysis] = []
        diagnostics: list[MetricReferenceUnavailable] = []
        for offset in context.reference_periods:
            window = reference_window(context.analysis_window, offset)
            self._record_phase("reference_acquisition")
            acquisition_started = self._monotonic_clock()
            try:
                acquired = await self._provider.acquire(context.provider_scope, window)
            except TimeoutError as error:
                self._emit_acquisition_failure(
                    context,
                    category="acquisition_timeout",
                    duration_ms=self._duration_ms(acquisition_started),
                    exception_type=type(error).__name__,
                    stage="reference_acquisition",
                )
                diagnostics.append(
                    MetricReferenceUnavailable(
                        offset=offset, category="acquisition", diagnostic=_diagnostic(error)
                    )
                )
                continue
            except Exception as error:
                self._emit_acquisition_failure(
                    context,
                    category="provider_failure",
                    duration_ms=self._duration_ms(acquisition_started),
                    exception_type=type(error).__name__,
                    stage="reference_acquisition",
                )
                diagnostics.append(
                    MetricReferenceUnavailable(
                        offset=offset, category="acquisition", diagnostic=_diagnostic(error)
                    )
                )
                continue
            if isinstance(
                acquired,
                (
                    MetricSeriesUnavailable,
                    MetricSeriesAcquisitionFailure,
                    MetricSeriesAcquisitionTimeout,
                ),
            ):
                self._emit_acquisition_failure(
                    context,
                    category=acquired.diagnostic_category,
                    duration_ms=self._duration_ms(acquisition_started),
                    attempt_count=acquired.attempt_count,
                    http_status=getattr(acquired, "http_status", None),
                    observed_series_count=getattr(acquired, "observed_series_count", None),
                    stage="reference_acquisition",
                )
                diagnostics.append(
                    MetricReferenceUnavailable(
                        offset=offset, category="acquisition", diagnostic=acquired.diagnostic
                    )
                )
                continue
            self._record_phase("reference_preparation")
            try:
                prepared = prepare_series(acquired.samples, window)
            except MetricSeriesMalformedError as error:
                diagnostics.append(
                    MetricReferenceUnavailable(
                        offset=offset, category="malformed", diagnostic=_diagnostic(error)
                    )
                )
                continue
            except Exception as error:
                diagnostics.append(
                    MetricReferenceUnavailable(
                        offset=offset, category="malformed", diagnostic=_diagnostic(error)
                    )
                )
                continue
            if isinstance(prepared, PreparedInsufficientSeries):
                diagnostics.append(
                    MetricReferenceUnavailable(
                        offset=offset,
                        category="insufficient",
                        diagnostic="fewer than three finite reference samples",
                    )
                )
                continue
            self._record_phase("reference_semanticization")
            try:
                reference_semantics = semanticize_mandatory(prepared, window)
            except Exception as error:
                diagnostics.append(
                    MetricReferenceUnavailable(
                        offset=offset, category="malformed", diagnostic=_diagnostic(error)
                    )
                )
                continue
            prepared_references.append(
                PreparedReferenceAnalysis(
                    offset=offset,
                    window=window,
                    prepared=prepared,
                    semantics=reference_semantics,
                )
            )
        return tuple(prepared_references), tuple(diagnostics)

    def _compare_references(
        self,
        *,
        current: PreparedUsableSeries,
        current_semantics: MetricSemantics,
        references: tuple[PreparedReferenceAnalysis, ...],
    ) -> tuple[
        tuple[MetricReferenceComparison, ...],
        tuple[MetricReferenceEvidence, ...],
        tuple[MetricReferenceUnavailable, ...],
    ]:
        comparisons: list[MetricReferenceComparison] = []
        evidence: list[MetricReferenceEvidence] = []
        diagnostics: list[MetricReferenceUnavailable] = []
        for reference in references:
            self._record_phase("reference_comparison")
            try:
                comparison, reference_evidence = compare_reference(
                    offset=reference.offset,
                    window=reference.window,
                    current=current,
                    current_semantics=current_semantics,
                    reference=reference.prepared,
                    reference_semantics=reference.semantics,
                )
            except Exception as error:
                diagnostics.append(
                    MetricReferenceUnavailable(
                        offset=reference.offset,
                        category="malformed",
                        diagnostic=_diagnostic(error),
                    )
                )
                continue
            comparisons.append(comparison)
            evidence.append(reference_evidence)
        return tuple(comparisons), tuple(evidence), tuple(diagnostics)

    def _failed_analysis(
        self, context: MetricLensExecutionContext, failure: MetricCurrentFailure
    ) -> MetricPreTransactionAnalysis:
        _, terminal_result = self._result_builder.failed(context, failure)
        return MetricPreTransactionAnalysis(
            context=context,
            prepared=None,
            semantics=None,
            dataset_ref=None,
            insufficient_agent_outcome=None,
            terminal_result=terminal_result,
            failure=failure,
        )

    def _emit_acquisition_failure(
        self,
        context: MetricLensExecutionContext,
        *,
        category: str,
        duration_ms: int,
        attempt_count: int | None = None,
        http_status: int | None = None,
        observed_series_count: int | None = None,
        exception_type: str | None = None,
        stage: str = "provider_acquisition",
    ) -> None:
        """Emit the sole safe current-Metric acquisition event for one pipeline attempt."""

        self._emitter.emit(
            DiagnosticEvent(
                event="metric_acquisition_failed",
                category=category,
                observation_run_id=context.identity.observation_run_id,
                lens_run_id=context.identity.lens_run_id,
                lens_id=context.identity.lens_id,
                source_id=context.provider_scope.source_id,
                stage=stage,
                component="metrics_pipeline",
                attempt_count=attempt_count,
                duration_ms=duration_ms,
                http_status=http_status,
                observed_series_count=observed_series_count,
                exception_type=exception_type,
            )
        )

    def _emit_failure(
        self,
        context: MetricLensExecutionContext,
        category: str,
        stage: str,
        error: BaseException,
    ) -> None:
        """Emit safe normalized Metric-stage failure metadata without agent/provider content."""
        self._emitter.emit(
            DiagnosticEvent(
                event="metric_failure_normalized",
                category=category,
                observation_run_id=context.identity.observation_run_id,
                lens_run_id=context.identity.lens_run_id,
                lens_id=context.identity.lens_id,
                source_id=context.provider_scope.source_id,
                agent_role="metric" if stage == "agent_execution" else None,
                stage=stage,
                component="metrics_pipeline",
                exception_type=type(error).__name__,
            )
        )

    def _duration_ms(self, started_at: float) -> int:
        """Return a non-negative bounded acquisition duration for operational logging."""

        return max(0, int((self._monotonic_clock() - started_at) * 1000))

    async def persist_terminal(
        self,
        session: AsyncSession,
        lens_run: LensRunModel,
        analysis: MetricPreTransactionAnalysis,
    ) -> LensAnalysisResultModel:
        """Read History, transition, and flush inside a transaction opened by the caller."""

        if lens_run.status != LensRunStatus.RUNNING.value:
            raise ValueError("Metric pipeline requires an already-running LensRun")
        if analysis.failure is not None:
            target = LensRunStatus.FAILED
            reason = StructuredReason(
                code=analysis.terminal_result.payload["status"]["error"]["code"]
            )
        elif isinstance(analysis.prepared, PreparedInsufficientSeries):
            target = LensRunStatus.COMPLETED
            reason = None
        else:
            self._record_phase("history_read")
            if analysis.semantics is None:
                raise RuntimeError("usable Metric analysis requires mandatory semantics")
            if not isinstance(analysis.prepared, PreparedUsableSeries):
                raise RuntimeError("usable Metric analysis requires prepared evidence")
            history_read = await self._history_reader.load(session, analysis.context)
            history = None
            history_evidence = None
            history_failed = False
            if isinstance(history_read, MetricHistoryCandidates):
                try:
                    history_sections = analyze_history(
                        analysis.context,
                        history_read.candidates,
                        MetricCurrentEvidence(**analysis.prepared.evidence.model_dump()),
                    )
                    if history_sections is not None:
                        history, history_evidence = history_sections
                except Exception:
                    history_failed = True
            if analysis.reference_diagnostics:
                target = LensRunStatus.PARTIAL
                reason = StructuredReason(
                    code="reference_unavailable", component="reference_periods"
                )
                _, terminal_result = self._result_builder.partial_reference_unavailable(
                    analysis.context,
                    analysis.prepared,
                    analysis.semantics,
                    analysis.reference_periods,
                    analysis.reference_evidence,
                    history,
                    history_evidence,
                    analysis.optional_projections,
                )
            elif history_failed:
                target = LensRunStatus.PARTIAL
                reason = StructuredReason(code="history_analysis_failed", component="history")
                _, terminal_result = self._result_builder.partial_history_analysis_failed(
                    analysis.context,
                    analysis.prepared,
                    analysis.semantics,
                    analysis.reference_periods,
                    analysis.reference_evidence,
                    analysis.optional_projections,
                )
            elif analysis.optional_failure_component is not None:
                target = LensRunStatus.PARTIAL
                reason = StructuredReason(
                    code="optional_analysis_failed",
                    component=analysis.optional_failure_component,
                )
                _, terminal_result = self._result_builder.partial_optional_analysis_failed(
                    analysis.context,
                    analysis.prepared,
                    analysis.semantics,
                    analysis.optional_failure_component,
                    analysis.optional_projections,
                    analysis.reference_periods,
                    analysis.reference_evidence,
                    history,
                    history_evidence,
                )
            else:
                target = LensRunStatus.COMPLETED
                reason = None
                _, terminal_result = self._result_builder.completed_sufficient(
                    analysis.context,
                    analysis.prepared,
                    analysis.semantics,
                    analysis.reference_periods,
                    analysis.reference_evidence,
                    history,
                    history_evidence,
                    analysis.optional_projections,
                )
            analysis = MetricPreTransactionAnalysis(
                context=analysis.context,
                prepared=analysis.prepared,
                semantics=analysis.semantics,
                dataset_ref=analysis.dataset_ref,
                insufficient_agent_outcome=analysis.insufficient_agent_outcome,
                terminal_result=terminal_result,
                failure=analysis.failure,
                reference_diagnostics=analysis.reference_diagnostics,
                reference_periods=analysis.reference_periods,
                reference_evidence=analysis.reference_evidence,
                optional_projections=analysis.optional_projections,
                optional_failure_component=analysis.optional_failure_component,
                agent_protocol_failure=analysis.agent_protocol_failure,
                tool_ledger=analysis.tool_ledger,
            )
        self._record_phase("lens_run_transition")
        if reason is None:
            await self._repository.advance_lens_run(session, lens_run, target)
        else:
            await self._repository.advance_lens_run(session, lens_run, target, reason=reason)
        self._record_phase("artifact_insertion_flush")
        return await self._repository.persist_lens_analysis_result(
            session, lens_run, analysis.terminal_result
        )


def _diagnostic(error: BaseException) -> str:
    """Keep transient failure detail bounded and outside the public result contract."""

    detail = str(error).strip() or type(error).__name__
    return detail[:512]
