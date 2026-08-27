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
    MetricCurrentAcquisitionFailed,
    MetricCurrentFailure,
    MetricCurrentSeriesMalformed,
    MetricLensExecutionContext,
    MetricMandatoryAnalysisFailure,
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
        try:
            _, terminal_result = self._result_builder.completed_sufficient(
                context, usable_prepared, semantics
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
        )

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
