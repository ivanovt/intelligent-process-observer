"""The sole constructor for the VS-01 completed-sufficient Metric artifact."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensResultIdentity,
    LensRunStatus,
    LensType,
)
from app.metrics.contracts import (
    CompletedInsufficientMetricResult,
    CompletedSufficientMetricResult,
    CurrentMetricAcquisitionFailedError,
    CurrentMetricSeriesMalformedError,
    FailedMetricResult,
    MandatoryMetricAnalysisFailedError,
    MetricCurrentAcquisitionFailed,
    MetricCurrentEvidence,
    MetricCurrentFailure,
    MetricCurrentSeriesMalformed,
    MetricCurrentState,
    MetricEvidenceSection,
    MetricFailedStatus,
    MetricHistory,
    MetricHistoryAnalysisFailedReason,
    MetricHistoryEvidence,
    MetricLensExecutionContext,
    MetricOptionalAnalysisFailedReason,
    MetricOptionalProjections,
    MetricReferenceComparison,
    MetricReferenceEvidence,
    MetricReferenceUnavailableReason,
    MetricResultProvenance,
    MetricSemantics,
    PartialMetricResult,
    PreparedUsableSeries,
)

UtcClock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


class MetricResultBuilder:
    def __init__(self, clock: UtcClock = utc_now) -> None:
        self._clock = clock

    def completed_sufficient(
        self,
        context: MetricLensExecutionContext,
        prepared: PreparedUsableSeries,
        semantics: MetricSemantics,
        reference_periods: tuple[MetricReferenceComparison, ...] = (),
        reference_evidence: tuple[MetricReferenceEvidence, ...] = (),
        history: MetricHistory | None = None,
        history_evidence: MetricHistoryEvidence | None = None,
        optional: MetricOptionalProjections | None = None,
    ) -> tuple[CompletedSufficientMetricResult, LensAnalysisResultInput]:
        if bool(reference_periods) != bool(reference_evidence):
            raise ValueError("reference semantics and evidence must co-occur")
        if (history is None) != (history_evidence is None):
            raise ValueError("history semantics and evidence must co-occur")
        current_state, current_evidence = _current_sections(prepared, semantics, optional)
        result = CompletedSufficientMetricResult(
            identity=context.identity,
            analysis_window=context.analysis_window,
            data_quality=prepared.data_quality,
            current_state=current_state,
            reference_periods=reference_periods or None,
            history=history,
            evidence=MetricEvidenceSection(
                current=current_evidence,
                reference_periods=reference_evidence or None,
                history=history_evidence,
            ),
            provenance=MetricResultProvenance(
                source=context.provider_scope.adapter_type,
                generated_at=self._clock(),
            ),
        )
        payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        envelope = LensAnalysisResultInput(
            result_type=LensType.METRIC,
            status=LensRunStatus.COMPLETED,
            schema_version=result.schema_version,
            identity=LensResultIdentity(**context.identity.model_dump()),
            provenance=result.provenance.model_dump(mode="json"),
            payload=payload,
        )
        return result, envelope

    def partial_reference_unavailable(
        self,
        context: MetricLensExecutionContext,
        prepared: PreparedUsableSeries,
        semantics: MetricSemantics,
        reference_periods: tuple[MetricReferenceComparison, ...],
        reference_evidence: tuple[MetricReferenceEvidence, ...],
        history: MetricHistory | None = None,
        history_evidence: MetricHistoryEvidence | None = None,
        optional: MetricOptionalProjections | None = None,
    ) -> tuple[PartialMetricResult, LensAnalysisResultInput]:
        """Build the first usable partial variant, owned only by reference completeness."""

        if bool(reference_periods) != bool(reference_evidence):
            raise ValueError("reference semantics and evidence must co-occur")
        if (history is None) != (history_evidence is None):
            raise ValueError("history semantics and evidence must co-occur")
        current_state, current_evidence = _current_sections(prepared, semantics, optional)
        result = PartialMetricResult(
            identity=context.identity,
            reason=MetricReferenceUnavailableReason(),
            analysis_window=context.analysis_window,
            data_quality=prepared.data_quality,
            current_state=current_state,
            reference_periods=reference_periods or None,
            history=history,
            evidence=MetricEvidenceSection(
                current=current_evidence,
                reference_periods=reference_evidence or None,
                history=history_evidence,
            ),
            provenance=MetricResultProvenance(
                source=context.provider_scope.adapter_type,
                generated_at=self._clock(),
            ),
        )
        payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        envelope = LensAnalysisResultInput(
            result_type=LensType.METRIC,
            status=LensRunStatus.PARTIAL,
            schema_version=result.schema_version,
            identity=LensResultIdentity(**context.identity.model_dump()),
            provenance=result.provenance.model_dump(mode="json"),
            payload=payload,
        )
        return result, envelope

    def partial_history_analysis_failed(
        self,
        context: MetricLensExecutionContext,
        prepared: PreparedUsableSeries,
        semantics: MetricSemantics,
        reference_periods: tuple[MetricReferenceComparison, ...] = (),
        reference_evidence: tuple[MetricReferenceEvidence, ...] = (),
        optional: MetricOptionalProjections | None = None,
    ) -> tuple[PartialMetricResult, LensAnalysisResultInput]:
        """Build the usable partial variant for an unexpected pure History failure."""

        if bool(reference_periods) != bool(reference_evidence):
            raise ValueError("reference semantics and evidence must co-occur")
        current_state, current_evidence = _current_sections(prepared, semantics, optional)
        result = PartialMetricResult(
            identity=context.identity,
            reason=MetricHistoryAnalysisFailedReason(),
            analysis_window=context.analysis_window,
            data_quality=prepared.data_quality,
            current_state=current_state,
            reference_periods=reference_periods or None,
            evidence=MetricEvidenceSection(
                current=current_evidence,
                reference_periods=reference_evidence or None,
            ),
            provenance=MetricResultProvenance(
                source=context.provider_scope.adapter_type,
                generated_at=self._clock(),
            ),
        )
        payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        envelope = LensAnalysisResultInput(
            result_type=LensType.METRIC,
            status=LensRunStatus.PARTIAL,
            schema_version=result.schema_version,
            identity=LensResultIdentity(**context.identity.model_dump()),
            provenance=result.provenance.model_dump(mode="json"),
            payload=payload,
        )
        return result, envelope

    def partial_optional_analysis_failed(
        self,
        context: MetricLensExecutionContext,
        prepared: PreparedUsableSeries,
        semantics: MetricSemantics,
        component: str,
        optional: MetricOptionalProjections,
        reference_periods: tuple[MetricReferenceComparison, ...] = (),
        reference_evidence: tuple[MetricReferenceEvidence, ...] = (),
        history: MetricHistory | None = None,
        history_evidence: MetricHistoryEvidence | None = None,
    ) -> tuple[PartialMetricResult, LensAnalysisResultInput]:
        """Build the tool-owned usable partial variant without transient diagnostics."""

        if bool(reference_periods) != bool(reference_evidence):
            raise ValueError("reference semantics and evidence must co-occur")
        if (history is None) != (history_evidence is None):
            raise ValueError("history semantics and evidence must co-occur")
        current_state, current_evidence = _current_sections(prepared, semantics, optional)
        result = PartialMetricResult(
            identity=context.identity,
            reason=MetricOptionalAnalysisFailedReason(component=component),
            analysis_window=context.analysis_window,
            data_quality=prepared.data_quality,
            current_state=current_state,
            reference_periods=reference_periods or None,
            history=history,
            evidence=MetricEvidenceSection(
                current=current_evidence,
                reference_periods=reference_evidence or None,
                history=history_evidence,
            ),
            provenance=MetricResultProvenance(
                source=context.provider_scope.adapter_type,
                generated_at=self._clock(),
            ),
        )
        payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        envelope = LensAnalysisResultInput(
            result_type=LensType.METRIC,
            status=LensRunStatus.PARTIAL,
            schema_version=result.schema_version,
            identity=LensResultIdentity(**context.identity.model_dump()),
            provenance=result.provenance.model_dump(mode="json"),
            payload=payload,
        )
        return result, envelope

    def completed_insufficient(
        self, context: MetricLensExecutionContext
    ) -> tuple[CompletedInsufficientMetricResult, LensAnalysisResultInput]:
        result = CompletedInsufficientMetricResult(
            identity=context.identity,
            analysis_window=context.analysis_window,
            data_quality="insufficient",
            provenance=MetricResultProvenance(
                source=context.provider_scope.adapter_type,
                generated_at=self._clock(),
            ),
        )
        payload = result.model_dump(mode="json", by_alias=True)
        envelope = LensAnalysisResultInput(
            result_type=LensType.METRIC,
            status=LensRunStatus.COMPLETED,
            schema_version=result.schema_version,
            identity=LensResultIdentity(**context.identity.model_dump()),
            provenance=result.provenance.model_dump(mode="json"),
            payload=payload,
        )
        return result, envelope

    def failed(
        self, context: MetricLensExecutionContext, failure: MetricCurrentFailure
    ) -> tuple[FailedMetricResult, LensAnalysisResultInput]:
        """Build the exact public failure from a typed, non-public stage outcome."""

        if isinstance(failure, MetricCurrentAcquisitionFailed):
            error = CurrentMetricAcquisitionFailedError()
        elif isinstance(failure, MetricCurrentSeriesMalformed):
            error = CurrentMetricSeriesMalformedError()
        else:
            error = MandatoryMetricAnalysisFailedError()
        result = FailedMetricResult(
            identity=context.identity,
            status=MetricFailedStatus(error=error),
            analysis_window=context.analysis_window,
            provenance=MetricResultProvenance(
                source=context.provider_scope.adapter_type,
                generated_at=self._clock(),
            ),
        )
        payload = result.model_dump(mode="json", by_alias=True)
        envelope = LensAnalysisResultInput(
            result_type=LensType.METRIC,
            status=LensRunStatus.FAILED,
            schema_version=result.schema_version,
            identity=LensResultIdentity(**context.identity.model_dump()),
            provenance=result.provenance.model_dump(mode="json"),
            payload=payload,
        )
        return result, envelope


def _current_sections(
    prepared: PreparedUsableSeries,
    semantics: MetricSemantics,
    optional: MetricOptionalProjections | None,
) -> tuple[MetricCurrentState, MetricCurrentEvidence]:
    projections = optional or MetricOptionalProjections()
    current_state = MetricCurrentState(
        trend=semantics.trend,
        variability=semantics.variability,
        spike=None if projections.spike is None else {"state": projections.spike.state},
        oscillation=None
        if projections.oscillation is None
        else {"state": projections.oscillation.state},
        stuck_signal=None
        if projections.stuck_signal is None
        else {"state": projections.stuck_signal.state},
    )
    current_evidence = MetricCurrentEvidence(
        **prepared.evidence.model_dump(),
        spike=None if projections.spike is None else projections.spike.evidence,
        oscillation=None if projections.oscillation is None else projections.oscillation.evidence,
        stuck_signal=None
        if projections.stuck_signal is None
        else projections.stuck_signal.evidence,
    )
    return current_state, current_evidence
