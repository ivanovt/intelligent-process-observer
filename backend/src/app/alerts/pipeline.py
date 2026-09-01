"""Pre-transaction Alert analysis pipeline."""

from __future__ import annotations

from collections.abc import Callable

from app.alerts.analyzer import analyze_current
from app.alerts.contracts import (
    AlertAgentRequest,
    AlertLensExecutionContext,
    AlertRecordsAvailable,
    AlertTerminalOutcome,
)
from app.alerts.normalization import normalize_current
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
        self._provider, self._agent = provider, agent
        self._result_builder, self._record_phase = (
            result_builder or AlertResultBuilder(),
            record_phase or (lambda _: None),
        )

    async def analyze(self, context: AlertLensExecutionContext) -> AlertTerminalOutcome:
        """Acquire, normalize, analyze, and build the completed Alert result."""
        if context.lens_run_status != "running":
            raise ValueError("Alert pipeline requires an existing running LensRun")
        if context.reference_periods:
            raise ValueError("configured Alert references are outside VS-02")
        self._record_phase("provider_acquisition")
        response = await self._provider.acquire(context.provider_scope, context.analysis_window)
        if not isinstance(response, AlertRecordsAvailable):
            raise ValueError("non-successful Alert acquisition is outside VS-02")
        self._record_phase("current_normalization")
        records = normalize_current(response, context.analysis_window, context.analysis_window.to)
        self._record_phase("mandatory_analysis")
        evidence = analyze_current(records)
        self._record_phase("zero_record_gate")
        if not evidence.record_count:
            self._record_phase("result_build")
            return self._result_builder.completed_zero(context, evidence)[1]
        self._record_phase("agent_completion")
        request = AlertAgentRequest(
            lens_name=context.lens_name,
            lens_description=context.lens_description,
            current_records=records,
            mandatory_evidence=evidence,
        )
        completion = await self._agent.complete(request)
        self._record_phase("result_build")
        return self._result_builder.completed(context, records, evidence, completion)[1]
