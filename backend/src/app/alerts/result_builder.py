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
from app.alerts.evidence_refs import resolve_evidence_references
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
        self._resolve_findings(completion, records, evidence)
        generated_at = self._clock()
        self._require_utc(generated_at, "generated_at")
        provenance = AlertResultProvenance(
            source_provider=context.provider_scope.source, generated_at=generated_at
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
        result = self._validate_completed_result(result, context)
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
        self._resolve_findings(completion, records, evidence)
        generated_at = self._clock()
        self._require_utc(generated_at, "generated_at")
        provenance = AlertResultProvenance(
            source_provider=context.provider_scope.source, generated_at=generated_at
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
        result = self._validate_partial_result(result, context)
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

    @staticmethod
    def _resolve_findings(
        completion: AlertAgentCompletion,
        records: tuple[CanonicalAlertRecord, ...],
        evidence: AlertMandatoryEvidence,
    ) -> None:
        """Validate every agent finding against final persisted Alert evidence."""
        for finding in completion.findings:
            if not finding.evidence_refs:
                raise ValueError("every Alert finding requires at least one evidence reference")
            resolve_evidence_references(finding.evidence_refs, records, evidence)

    @staticmethod
    def _validate_completed_result(
        result: CompletedAlertAnalysisResult, context: AlertLensExecutionContext
    ) -> CompletedAlertAnalysisResult:
        """Revalidate a final completed payload and its immutable execution context."""
        validated = CompletedAlertAnalysisResult.model_validate(result.model_dump(by_alias=True))
        AlertResultBuilder._validate_context_correlation(validated, context)
        return validated

    @staticmethod
    def _validate_partial_result(
        result: PartialAlertAnalysisResult, context: AlertLensExecutionContext
    ) -> PartialAlertAnalysisResult:
        """Revalidate a final partial payload and its immutable execution context."""
        validated = PartialAlertAnalysisResult.model_validate(result.model_dump(by_alias=True))
        AlertResultBuilder._validate_context_correlation(validated, context)
        return validated

    @staticmethod
    def _validate_context_correlation(
        result: CompletedAlertAnalysisResult, context: AlertLensExecutionContext
    ) -> None:
        """Require final result metadata and comparison order to match its context."""
        for value, field in (
            (context.analysis_window.from_, "analysis_window.from"),
            (context.analysis_window.to, "analysis_window.to"),
            (result.analysis_timestamp, "analysis_timestamp"),
            (result.analysis_window.from_, "result analysis_window.from"),
            (result.analysis_window.to, "result analysis_window.to"),
            (result.provenance.generated_at, "provenance.generated_at"),
        ):
            AlertResultBuilder._require_utc(value, field)
        if result.identity != context.identity:
            raise ValueError("result identity must match execution context")
        if result.analysis_timestamp != context.analysis_window.to:
            raise ValueError("analysis_timestamp must equal execution window end")
        if result.analysis_window != context.analysis_window:
            raise ValueError("analysis_window must match execution context")
        if result.provenance.source_provider != context.provider_scope.source:
            raise ValueError("result provenance must match provider scope")
        offsets = tuple(comparison.offset for comparison in result.comparisons)
        configured = context.reference_periods
        if len(offsets) != len(set(offsets)) or (
            configured and offsets != tuple(offset for offset in configured if offset in offsets)
        ):
            raise ValueError("comparisons must be unique and in configured reference order")

    @staticmethod
    def _require_utc(value: datetime, field: str) -> None:
        """Reject non-UTC timestamps at the immutable final-result boundary."""
        if value.tzinfo is not UTC:
            raise ValueError(f"{field} must use UTC")
