"""Pre-transaction Alert analysis pipeline."""

from __future__ import annotations

from collections.abc import Callable
from inspect import signature

from pydantic import ValidationError

from app.alerts.analyzer import analyze_current
from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAgentRequest,
    AlertLensExecutionContext,
    AlertProviderTimeout,
    AlertRecordsAvailable,
    AlertTerminalOutcome,
)
from app.alerts.normalization import normalize_current_with_rejections
from app.alerts.ports import AlertAnalysisAgent, AlertProvider
from app.alerts.references import acquire_comparisons
from app.alerts.result_builder import AlertResultBuilder
from app.alerts.tools import AlertOptionalToolRegistry, unsuccessful_trace
from app.infrastructure.persistence.runtime_contracts import LensRunStatus, StructuredReason

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
        analyzer: Callable = analyze_current,
        tool_registry_factory: Callable[
            [tuple, object], AlertOptionalToolRegistry
        ] = AlertOptionalToolRegistry,
    ) -> None:
        self._provider, self._agent = provider, agent
        self._result_builder, self._record_phase = (
            result_builder or AlertResultBuilder(),
            record_phase or (lambda _: None),
        )
        self._analyzer = analyzer
        self._tool_registry_factory = tool_registry_factory or AlertOptionalToolRegistry

    @staticmethod
    def _failed(code: str, component: str | None = None) -> AlertTerminalOutcome:
        """Return the artifact-free terminal outcome for one mandatory failure."""
        return AlertTerminalOutcome(
            status=LensRunStatus.FAILED,
            reason=StructuredReason(code=code, component=component),
        )

    async def analyze(self, context: AlertLensExecutionContext) -> AlertTerminalOutcome:
        """Acquire, normalize, analyze, and build the completed Alert result."""
        if context.lens_run_status != "running":
            raise ValueError("Alert pipeline requires an existing running LensRun")
        self._record_phase("provider_acquisition")
        try:
            response = await self._provider.acquire(context.provider_scope, context.analysis_window)
        except TimeoutError:
            return self._failed("current_query_timeout")
        except Exception:
            return self._failed("current_query_failed")
        if isinstance(response, AlertProviderTimeout):
            return self._failed("current_query_timeout")
        if not isinstance(response, AlertRecordsAvailable):
            return self._failed("current_query_failed")
        self._record_phase("current_normalization")
        records, current_rejected = normalize_current_with_rejections(
            response, context.analysis_window, context.analysis_window.to
        )
        if response.records and not records:
            return self._failed("invalid_records", "current_normalization")
        self._record_phase("mandatory_analysis")
        try:
            evidence = self._analyzer(records)
        except Exception:
            return self._failed("deterministic_analysis_failed")
        self._record_phase("reference_acquisition")
        comparisons, reference_unavailable = await acquire_comparisons(
            self._provider,
            context.provider_scope,
            context.analysis_window,
            evidence,
            context.reference_periods,
        )
        evidence = evidence.model_copy(update={"comparisons": comparisons})
        self._record_phase("zero_record_gate")
        if not evidence.record_count:
            self._record_phase("result_build")
            try:
                return self._result_builder.usable(
                    context, (), evidence, None, current_rejected, reference_unavailable, zero=True
                )[1]
            except ValueError:
                return self._failed("result_validation_failed", "alert_result_builder")
        self._record_phase("agent_completion")
        request = AlertAgentRequest(
            lens_name=context.lens_name,
            lens_description=context.lens_description,
            current_records=records,
            mandatory_evidence=evidence,
            comparisons=comparisons,
        )
        tools = self._tool_registry_factory(records, evidence)
        try:
            complete = self._agent.complete
            completion = await (
                complete(request, tools)
                if len(signature(complete).parameters) > 1
                else complete(request)
            )
        except TimeoutError:
            return self._failed("agent_timeout")
        except Exception:
            return self._failed("agent_failed")
        try:
            completion = AlertAgentCompletion.model_validate(completion)
        except ValidationError:
            return self._failed("agent_failed")
        self._record_phase("result_build")
        try:
            return self._result_builder.usable(
                context,
                records,
                evidence,
                completion,
                current_rejected,
                reference_unavailable,
                unsuccessful_calls=unsuccessful_trace(tools.ledger),
            )[1]
        except ValueError:
            return self._failed("result_validation_failed", "alert_result_builder")
