"""Strict construction of Alert result artifacts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.alerts.contracts import (
    AlertActivity,
    AlertLensExecutionContext,
    AlertMandatoryEvidence,
    AlertResultProvenance,
    AlertStatusDistribution,
    AlertTerminalOutcome,
    CompletedZeroAlertAnalysisResult,
)
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensResultIdentity,
    LensRunStatus,
    LensType,
)


class AlertResultBuilder:
    """Sole constructor of strict Alert result and persistence-envelope values."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def completed_zero(
        self, context: AlertLensExecutionContext, evidence: AlertMandatoryEvidence
    ) -> tuple[CompletedZeroAlertAnalysisResult, AlertTerminalOutcome]:
        """Build the completed zero-record result and its correlated generic envelope."""

        if evidence.record_count != 0 or evidence.occurrence_count != 0:
            raise ValueError("zero-record builder requires zero mandatory evidence")
        provenance = AlertResultProvenance(
            source_provider=context.provider_scope.source, generated_at=self._clock()
        )
        result = CompletedZeroAlertAnalysisResult(
            identity=context.identity,
            analysis_timestamp=context.analysis_window.to,
            analysis_window=context.analysis_window,
            alert_activity=AlertActivity(
                record_count=evidence.record_count,
                occurrence_count=evidence.occurrence_count,
            ),
            status_distribution=AlertStatusDistribution(**evidence.status_counts),
            provenance=provenance,
        )
        payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        envelope = LensAnalysisResultInput(
            result_type=LensType.ALERT,
            status=LensRunStatus.COMPLETED,
            schema_version=result.schema_version,
            identity=LensResultIdentity(**context.identity.model_dump()),
            provenance=provenance.model_dump(mode="json"),
            payload=payload,
        )
        return result, AlertTerminalOutcome(artifact=envelope)
