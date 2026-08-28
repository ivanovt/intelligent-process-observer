"""Deterministic VS-01 Metric walking-skeleton application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models import LensAnalysisResultModel, LensRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensRunStatus,
    StructuredReason,
)
from app.metrics.contracts import (
    FIXED_ALLOWED_TOOLS,
    MetricAgentCompletion,
    MetricAgentInsufficientRequest,
    MetricAgentOperationalFailure,
    MetricAgentUsableRequest,
    MetricAnalysisWindow,
    MetricCurrentAcquisitionFailed,
    MetricCurrentFailure,
    MetricCurrentSeriesMalformed,
    MetricLensExecutionContext,
    MetricMandatoryAnalysisFailure,
    MetricReferenceComparison,
    MetricReferenceEvidence,
    MetricReferenceUnavailable,
    MetricSemantics,
    MetricSeriesAcquisitionFailure,
    MetricSeriesAcquisitionTimeout,
    MetricSeriesUnavailable,
    PreparedInsufficientSeries,
    PreparedSeries,
    PreparedUsableSeries,
)
from app.metrics.ports import MetricHistoryReader, MetricsAnalysisAgent, MetricSeriesProvider
from app.metrics.preprocessing import MetricSeriesMalformedError, prepare_series
from app.metrics.references import compare_reference, reference_window
from app.metrics.result_builder import MetricResultBuilder
from app.metrics.semantics import semanticize_mandatory

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
    ) -> None:
        self._provider = provider
        self._agent = agent
        self._history_reader = history_reader
        self._repository = repository
        self._result_builder = result_builder or MetricResultBuilder()
        self._record_phase = record_phase or (lambda _: None)

    async def analyze(self, context: MetricLensExecutionContext) -> MetricPreTransactionAnalysis:
        """Perform the stages that must not hold the History/write transaction open."""

        self._record_phase("provider_acquisition")
        try:
            available = await self._provider.acquire(
                context.provider_scope, context.analysis_window
            )
        except TimeoutError as error:
            return self._failed_analysis(
                context, MetricCurrentAcquisitionFailed(diagnostic=_diagnostic(error))
            )
        except Exception as error:
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
            return self._failed_analysis(
                context, MetricCurrentAcquisitionFailed(diagnostic=available.diagnostic)
            )
        self._record_phase("current_preparation")
        try:
            prepared = prepare_series(available.samples, context.analysis_window)
        except MetricSeriesMalformedError as error:
            return self._failed_analysis(
                context, MetricCurrentSeriesMalformed(diagnostic=_diagnostic(error))
            )
        except Exception as error:
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
            except Exception:
                completion = MetricAgentOperationalFailure()
            try:
                _, terminal_result = self._result_builder.completed_insufficient(context)
            except Exception as error:
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
            return self._failed_analysis(
                context, MetricMandatoryAnalysisFailure(diagnostic=_diagnostic(error))
            )
        prepared_references, reference_diagnostics = await self._prepare_references(context)
        dataset_ref = uuid4().hex
        request = MetricAgentUsableRequest(
            identity=context.identity,
            analysis_window=context.analysis_window,
            analysis_objectives=context.analysis_objectives,
            data_quality=usable_prepared.data_quality,
            evidence=usable_prepared.evidence,
            semantics=semantics,
            allowed_tools=FIXED_ALLOWED_TOOLS,
            dataset_ref=dataset_ref,
        )
        self._record_phase("agent_execution")
        completion = await self._agent.complete(request)
        MetricAgentCompletion.model_validate(completion)
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
                )
            else:
                _, terminal_result = self._result_builder.completed_sufficient(
                    context,
                    usable_prepared,
                    semantics,
                    comparisons,
                    reference_evidence,
                )
        except Exception as error:
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
            try:
                acquired = await self._provider.acquire(context.provider_scope, window)
            except TimeoutError as error:
                diagnostics.append(
                    MetricReferenceUnavailable(
                        offset=offset, category="acquisition", diagnostic=_diagnostic(error)
                    )
                )
                continue
            except Exception as error:
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
            await self._history_reader.load_empty(session, analysis.context)
            if analysis.semantics is None:
                raise RuntimeError("usable Metric analysis requires mandatory semantics")
            if analysis.reference_diagnostics:
                target = LensRunStatus.PARTIAL
                reason = StructuredReason(
                    code="reference_unavailable", component="reference_periods"
                )
            else:
                target = LensRunStatus.COMPLETED
                reason = None
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
