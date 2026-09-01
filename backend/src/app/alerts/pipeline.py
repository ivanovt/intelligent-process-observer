"""Pre-transaction Alert analysis walking skeleton."""

from __future__ import annotations

from collections.abc import Callable

from app.alerts.analyzer import analyze_zero_records
from app.alerts.contracts import (
    AlertLensExecutionContext,
    AlertRecordsAvailable,
    AlertTerminalOutcome,
)
from app.alerts.normalization import normalize_empty_current
from app.alerts.ports import AlertAnalysisAgent, AlertProvider
from app.alerts.result_builder import AlertResultBuilder

PhaseRecorder = Callable[[str], None]


class AlertAnalysisPipeline:
    """Analyze a running Alert LensRun before any write transaction is opened."""

    def __init__(
        self,
        *,
        provider: AlertProvider,
        agent: AlertAnalysisAgent,
        result_builder: AlertResultBuilder | None = None,
        record_phase: PhaseRecorder | None = None,
    ) -> None:
        self._provider = provider
        self._agent = agent
        self._result_builder = result_builder or AlertResultBuilder()
        self._record_phase = record_phase or (lambda _: None)

    async def analyze(self, context: AlertLensExecutionContext) -> AlertTerminalOutcome:
        """Acquire, analyze, and build the successful empty result without calling the agent."""

        if context.lens_run_status != "running":
            raise ValueError("Alert pipeline requires an existing running LensRun")
        if context.reference_periods:
            raise ValueError("configured Alert references are outside VS-01")
        self._record_phase("provider_acquisition")
        response = await self._provider.acquire(context.provider_scope, context.analysis_window)
        if not isinstance(response, AlertRecordsAvailable):
            raise ValueError("non-successful Alert acquisition is outside VS-01")
        self._record_phase("current_normalization")
        records = normalize_empty_current(response)
        self._record_phase("mandatory_analysis")
        evidence = analyze_zero_records(records)
        self._record_phase("zero_record_gate")
        self._record_phase("result_build")
        _, outcome = self._result_builder.completed_zero(context, evidence)
        return outcome
