"""Strict construction of Alert result artifacts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertLensExecutionContext,
    AlertMandatoryEvidence,
    AlertOptionalToolExecution,
    AlertResultProvenance,
    AlertTerminalOutcome,
    CanonicalAlertRecord,
    CompletedAlertAnalysisResult,
    PartialAlertAnalysisResult,
)
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensResultIdentity,
    LensRunStatus,
    LensType,
    StructuredReason,
)


class AlertResultBuilder:
    """Sole constructor of strict Alert result and persistence-envelope values."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def completed_zero(
        self, context: AlertLensExecutionContext, evidence: AlertMandatoryEvidence
    ) -> tuple[CompletedAlertAnalysisResult, AlertTerminalOutcome]:
        """Build the completed zero-record result and its correlated generic envelope."""
        return self.completed(
            context,
            (),
            evidence,
            AlertAgentCompletion(findings=(), overall_importance="low"),
            zero=True,
        )

    def completed(
        self,
        context: AlertLensExecutionContext,
        records: tuple[CanonicalAlertRecord, ...],
        evidence: AlertMandatoryEvidence,
        completion: AlertAgentCompletion,
        *,
        zero: bool = False,
        unsuccessful_calls: tuple[dict[str, str], ...] = (),
    ) -> tuple[CompletedAlertAnalysisResult, AlertTerminalOutcome]:
        """Build the completed strict artifact from canonical records and bounded output."""
        if zero:
            completion = completion.model_copy(update={"overall_importance": "none"})
        if evidence.record_count != len(records):
            raise ValueError("evidence record_count must match canonical records")
        allowed = {
            "alert_activity",
            "status_distribution",
            "duration_statistics",
            "provider_importance_distribution",
        } | {f"alerts.{record.id}" for record in records}
        if any(
            ref not in allowed for finding in completion.findings for ref in finding.evidence_refs
        ):
            raise ValueError("finding evidence ref does not resolve to this Alert result")
        provenance = AlertResultProvenance(
            source_provider=context.provider_scope.source, generated_at=self._clock()
        )
        result = CompletedAlertAnalysisResult(
            identity=context.identity,
            analysis_timestamp=context.analysis_window.to,
            analysis_window=context.analysis_window,
            alerts=records,
            alert_activity=evidence.alert_activity,
            status_distribution=evidence.status_distribution,
            duration_statistics=evidence.duration_statistics,
            provider_importance_distribution=evidence.provider_importance_distribution,
            comparisons=evidence.comparisons,
            optional_tool_execution=(
                AlertOptionalToolExecution(unsuccessful_calls=unsuccessful_calls)
                if unsuccessful_calls
                else None
            ),
            findings=completion.findings,
            overall_importance=completion.overall_importance,
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

    def usable(
        self,
        context: AlertLensExecutionContext,
        records: tuple[CanonicalAlertRecord, ...],
        evidence: AlertMandatoryEvidence,
        completion: AlertAgentCompletion | None,
        current_rejected: bool,
        reference_unavailable: bool,
        *,
        zero: bool = False,
        unsuccessful_calls: tuple[dict[str, str], ...] = (),
    ) -> tuple[CompletedAlertAnalysisResult | PartialAlertAnalysisResult, AlertTerminalOutcome]:
        """Build the completed or primary-reason partial artifact from usable evidence."""
        if completion is None:
            completion = AlertAgentCompletion(findings=(), overall_importance="low")
            zero = True
        if zero:
            completion = completion.model_copy(update={"overall_importance": "none"})
        reason = (
            StructuredReason(code="invalid_records", component="current_normalization")
            if current_rejected
            else StructuredReason(code="reference_unavailable", component="reference_periods")
            if reference_unavailable
            else None
        )
        if reason is None:
            return self.completed(
                context,
                records,
                evidence,
                completion,
                zero=zero,
                unsuccessful_calls=unsuccessful_calls,
            )
        if evidence.record_count != len(records):
            raise ValueError("evidence record_count must match canonical records")
        allowed = {
            "alert_activity",
            "status_distribution",
            "duration_statistics",
            "provider_importance_distribution",
        } | {f"alerts.{record.id}" for record in records}
        if any(
            ref not in allowed for finding in completion.findings for ref in finding.evidence_refs
        ):
            raise ValueError("finding evidence ref does not resolve to this Alert result")
        provenance = AlertResultProvenance(
            source_provider=context.provider_scope.source, generated_at=self._clock()
        )
        result = PartialAlertAnalysisResult(
            identity=context.identity,
            analysis_timestamp=context.analysis_window.to,
            analysis_window=context.analysis_window,
            alerts=records,
            alert_activity=evidence.alert_activity,
            status_distribution=evidence.status_distribution,
            duration_statistics=evidence.duration_statistics,
            provider_importance_distribution=evidence.provider_importance_distribution,
            comparisons=evidence.comparisons,
            optional_tool_execution=(
                AlertOptionalToolExecution(unsuccessful_calls=unsuccessful_calls)
                if unsuccessful_calls
                else None
            ),
            findings=completion.findings,
            overall_importance=completion.overall_importance,
            provenance=provenance,
            reason=reason,
        )
        envelope = LensAnalysisResultInput(
            result_type=LensType.ALERT,
            status=LensRunStatus.PARTIAL,
            schema_version=result.schema_version,
            identity=LensResultIdentity(**context.identity.model_dump()),
            provenance=provenance.model_dump(mode="json"),
            payload=result.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        return result, AlertTerminalOutcome(
            status=LensRunStatus.PARTIAL, reason=reason, artifact=envelope
        )
