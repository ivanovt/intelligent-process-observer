"""Deterministic VS-01 Metric walking-skeleton application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models import LensAnalysisResultModel, LensRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import LensRunStatus
from app.metrics.contracts import (
    FIXED_ALLOWED_TOOLS,
    MetricAgentCompletion,
    MetricAgentInsufficientRequest,
    MetricAgentOperationalFailure,
    MetricAgentUsableRequest,
    MetricLensExecutionContext,
    MetricSemantics,
    PreparedInsufficientSeries,
    PreparedSeries,
    PreparedUsableSeries,
)
from app.metrics.ports import MetricHistoryReader, MetricsAnalysisAgent, MetricSeriesProvider
from app.metrics.preprocessing import prepare_series
from app.metrics.result_builder import MetricResultBuilder
from app.metrics.semantics import semanticize_mandatory

PhaseRecorder = Callable[[str], None]


@dataclass(frozen=True)
class MetricPreTransactionAnalysis:
    context: MetricLensExecutionContext
    prepared: PreparedSeries
    semantics: MetricSemantics | None
    dataset_ref: str | None
    insufficient_agent_outcome: MetricAgentCompletion | MetricAgentOperationalFailure | None


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
        available = await self._provider.acquire(context.provider_scope, context.analysis_window)
        self._record_phase("current_preparation")
        prepared = prepare_series(available.samples, context.analysis_window)
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
            return MetricPreTransactionAnalysis(
                context=context,
                prepared=prepared,
                semantics=None,
                dataset_ref=None,
                insufficient_agent_outcome=completion,
            )

        usable_prepared: PreparedUsableSeries = prepared
        self._record_phase("mandatory_semanticization")
        semantics = semanticize_mandatory(usable_prepared, context.analysis_window)
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
        return MetricPreTransactionAnalysis(
            context=context,
            prepared=usable_prepared,
            semantics=semantics,
            dataset_ref=dataset_ref,
            insufficient_agent_outcome=None,
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
        if isinstance(analysis.prepared, PreparedInsufficientSeries):
            _, envelope = self._result_builder.completed_insufficient(analysis.context)
        else:
            self._record_phase("history_read")
            await self._history_reader.load_empty(session, analysis.context)
            if analysis.semantics is None:
                raise RuntimeError("usable Metric analysis requires mandatory semantics")
            _, envelope = self._result_builder.completed_sufficient(
                analysis.context, analysis.prepared, analysis.semantics
            )
        self._record_phase("lens_run_transition")
        await self._repository.advance_lens_run(session, lens_run, LensRunStatus.COMPLETED)
        self._record_phase("artifact_insertion_flush")
        return await self._repository.persist_lens_analysis_result(session, lens_run, envelope)
