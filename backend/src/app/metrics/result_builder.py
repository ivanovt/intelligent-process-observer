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
    CompletedSufficientMetricResult,
    MetricCurrentEvidence,
    MetricCurrentState,
    MetricEvidenceSection,
    MetricLensExecutionContext,
    MetricResultProvenance,
    MetricSemantics,
    PreparedGoodSeries,
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
        prepared: PreparedGoodSeries,
        semantics: MetricSemantics,
    ) -> tuple[CompletedSufficientMetricResult, LensAnalysisResultInput]:
        evidence = prepared.evidence
        result = CompletedSufficientMetricResult(
            identity=context.identity,
            analysis_window=context.analysis_window,
            data_quality="good",
            current_state=MetricCurrentState(
                trend=semantics.trend, variability=semantics.variability
            ),
            evidence=MetricEvidenceSection(current=MetricCurrentEvidence(**evidence.model_dump())),
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
