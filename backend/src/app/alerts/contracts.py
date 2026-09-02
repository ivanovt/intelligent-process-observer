"""Strict, framework-neutral contracts for the Alert analysis pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite
from typing import Any, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensRunStatus,
    StructuredReason,
)


class StrictAlertModel(BaseModel):
    """Base model that rejects unknown Alert contract fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


class AlertIdentity(StrictAlertModel):
    """Immutable runtime identity of one Alert analysis."""

    observation_id: UUID
    observation_run_id: UUID
    lens_id: str = Field(min_length=1)
    lens_run_id: UUID


class AlertAnalysisWindow(StrictAlertModel):
    """UTC interval selected by the existing LensRun."""

    from_: datetime = Field(
        validation_alias=AliasChoices("from", "start"), serialization_alias="start"
    )
    to: datetime = Field(validation_alias=AliasChoices("to", "end"), serialization_alias="end")

    @field_validator("from_", "to")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_order(self) -> AlertAnalysisWindow:
        if self.from_ >= self.to:
            raise ValueError("analysis_window.from must be before analysis_window.to")
        return self


class AlertProviderScope(StrictAlertModel):
    """Opaque frozen provider source and selector scope."""

    source: str = Field(min_length=1)
    query: str = Field(min_length=1)


class AlertLensExecutionContext(StrictAlertModel):
    """All immutable inputs permitted to one Alert pipeline execution."""

    identity: AlertIdentity
    provider_scope: AlertProviderScope
    analysis_window: AlertAnalysisWindow
    lens_name: str = Field(min_length=1)
    lens_description: str | None = None
    analysis_objectives: tuple[str, ...] = ()
    reference_periods: tuple[str, ...] = ()
    lens_run_status: Literal["running"] = "running"

    @field_validator("reference_periods")
    @classmethod
    def validate_reference_periods(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Accept unique positive configured offsets used by reference acquisition."""
        import re

        if len(values) != len(set(values)) or any(
            re.fullmatch(r"[1-9][0-9]*(m|h|d|w)", value) is None for value in values
        ):
            raise ValueError("reference_periods must contain unique positive m, h, d, or w offsets")
        return values


class AlertProviderImportance(StrictAlertModel):
    """Provider-native importance value retained without interpretation."""

    type: str = Field(min_length=1)
    value: str = Field(min_length=1)


class AlertProviderRecord(StrictAlertModel):
    """Transport-neutral raw Alert record accepted from a provider port."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    source_status: str = Field(min_length=1)
    provider_importance: AlertProviderImportance | None = None
    occurrence_count: int | None = Field(default=None, ge=0)
    source_ref: str | None = None

    @field_validator("started_at", "ended_at")
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> AlertProviderRecord:
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must not precede started_at")
        return self


class AlertRecordsAvailable(StrictAlertModel):
    """Successful provider acquisition containing raw Alert records."""

    # Provider mapping can leave malformed values for application-owned normalization.
    records: tuple[AlertProviderRecord | dict[str, Any], ...] = ()
    source: str = Field(min_length=1)


class AlertProviderUnavailable(StrictAlertModel):
    """Typed unavailable outcome for a non-current provider request."""

    state: Literal["unavailable"] = "unavailable"
    diagnostic: str = Field(min_length=1, max_length=512)


class AlertProviderFailure(StrictAlertModel):
    """Typed provider failure outcome with transient diagnostics."""

    state: Literal["failed"] = "failed"
    diagnostic: str = Field(min_length=1, max_length=512)


class AlertProviderTimeout(StrictAlertModel):
    """Typed provider timeout outcome with transient diagnostics."""

    state: Literal["timeout"] = "timeout"
    diagnostic: str = Field(min_length=1, max_length=512)


AlertProviderOutcome = (
    AlertRecordsAvailable | AlertProviderUnavailable | AlertProviderFailure | AlertProviderTimeout
)


class AlertStatus(StrictAlertModel):
    """Canonical Alert lifecycle status derived from provider fields."""

    normalized: Literal["active", "resolved", "unknown"]
    source: str = Field(min_length=1)


class CanonicalAlertRecord(StrictAlertModel):
    """Validated Alert record used by deterministic and agent stages."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: float = Field(ge=0)
    status: AlertStatus
    provider_importance: AlertProviderImportance | None = None
    occurrence_count: int | None = Field(default=None, ge=0)
    source_ref: str | None = None

    @field_validator("started_at", "ended_at")
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        return _utc(value) if value is not None else None


class AlertActivity(StrictAlertModel):
    """Deterministic current-record and occurrence totals."""

    record_count: int = Field(ge=0)
    occurrence_count: int = Field(ge=0)


class AlertStatusDistribution(StrictAlertModel):
    """Deterministic distribution of canonical lifecycle statuses."""

    active: int = Field(ge=0)
    resolved: int = Field(ge=0)
    unknown: int = Field(ge=0)


class AlertDurationStatistics(StrictAlertModel):
    """Finite duration aggregates for non-empty Alert evidence."""

    min_seconds: float = Field(ge=0, allow_inf_nan=False)
    max_seconds: float = Field(ge=0, allow_inf_nan=False)
    average_seconds: float = Field(ge=0, allow_inf_nan=False)


class AlertProviderImportanceDistribution(StrictAlertModel):
    """Grouped native provider importance values for current records."""

    type: str = Field(min_length=1)
    values: dict[str, int] = Field(min_length=1)


class AlertMandatoryEvidence(StrictAlertModel):
    """Deterministic evidence required before Alert agent completion."""

    alert_activity: AlertActivity = Field(
        default_factory=lambda: AlertActivity(record_count=0, occurrence_count=0)
    )
    status_distribution: AlertStatusDistribution = Field(
        default_factory=lambda: AlertStatusDistribution(active=0, resolved=0, unknown=0)
    )
    duration_statistics: AlertDurationStatistics | None = None
    provider_importance_distribution: AlertProviderImportanceDistribution | None = None
    comparisons: tuple[AlertReferenceComparison, ...] = ()

    @property
    def record_count(self) -> int:
        """Return the current record cardinality used by the agent gate."""
        return self.alert_activity.record_count

    @property
    def occurrence_count(self) -> int:
        """Return the deterministic effective occurrence total."""
        return self.alert_activity.occurrence_count


class AlertFinding(StrictAlertModel):
    """One agent finding grounded in canonical Alert evidence references."""

    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class AlertAgentRequest(StrictAlertModel):
    """Strict bounded projection delivered to the Alert analysis agent."""

    lens_name: str = Field(min_length=1)
    lens_description: str | None = None
    current_records: tuple[CanonicalAlertRecord, ...]
    mandatory_evidence: AlertMandatoryEvidence
    comparisons: tuple[AlertReferenceComparison, ...] = ()


AlertOptionalToolName = Literal[
    "recurrence_concentration_analysis",
    "duration_outlier_analysis",
    "reference_pattern_analysis",
]


class RecurrenceConcentrationToolDescriptor(StrictAlertModel):
    """Descriptor for the admitted recurrence optional tool."""

    name: Literal["recurrence_concentration_analysis"] = "recurrence_concentration_analysis"


class DurationOutlierToolDescriptor(StrictAlertModel):
    """Descriptor for the admitted duration-outlier optional tool."""

    name: Literal["duration_outlier_analysis"] = "duration_outlier_analysis"


class ReferencePatternToolDescriptor(StrictAlertModel):
    """Descriptor for the admitted reference-pattern optional tool."""

    name: Literal["reference_pattern_analysis"] = "reference_pattern_analysis"


AlertOptionalToolDescriptors = tuple[
    RecurrenceConcentrationToolDescriptor,
    DurationOutlierToolDescriptor,
    ReferencePatternToolDescriptor,
]
FIXED_ALERT_OPTIONAL_TOOLS: AlertOptionalToolDescriptors = (
    RecurrenceConcentrationToolDescriptor(),
    DurationOutlierToolDescriptor(),
    ReferencePatternToolDescriptor(),
)


class AlertOptionalToolSuccess(StrictAlertModel):
    """Successful optional-tool execution outcome."""

    name: AlertOptionalToolName
    outcome: Literal["success"] = "success"
    data: dict[str, Any]


class AlertOptionalToolNotApplicable(StrictAlertModel):
    """Optional-tool outcome for valid but inapplicable evidence."""

    name: AlertOptionalToolName
    outcome: Literal["not_applicable"] = "not_applicable"
    data: dict[str, Any] = Field(default_factory=dict)


class AlertOptionalToolFailed(StrictAlertModel):
    """Best-effort optional-tool failure outcome."""

    name: AlertOptionalToolName
    outcome: Literal["failed"] = "failed"
    diagnostic: str = Field(min_length=1, max_length=512)


class AlertOptionalToolTimedOut(StrictAlertModel):
    """Best-effort optional-tool timeout outcome."""

    name: AlertOptionalToolName
    outcome: Literal["timeout"] = "timeout"
    diagnostic: str = Field(min_length=1, max_length=512)


class AlertOptionalToolRejected(StrictAlertModel):
    """Rejected optional-tool request that never executes an evaluator."""

    outcome: Literal["rejected"] = "rejected"
    reason: Literal["unregistered", "invalid_arguments", "over_budget"]


AlertOptionalToolExecutionOutcome = (
    AlertOptionalToolSuccess
    | AlertOptionalToolNotApplicable
    | AlertOptionalToolFailed
    | AlertOptionalToolTimedOut
)
AlertOptionalToolOutcome = AlertOptionalToolExecutionOutcome | AlertOptionalToolRejected


class AlertOptionalToolAttempt(StrictAlertModel):
    """One budgeted optional-tool request and its outcome."""

    ordinal: int = Field(gt=0)
    requested_name: str = Field(min_length=1)
    outcome: AlertOptionalToolOutcome
    executed: bool


class AlertUnsuccessfulToolCall(StrictAlertModel):
    """Persistable minimal trace of an unsuccessful optional-tool call."""

    tool: AlertOptionalToolName
    status: Literal["failed", "timeout"]


class AlertOptionalToolExecution(StrictAlertModel):
    """Optional-tool trace section included only when unsuccessful calls exist."""

    unsuccessful_calls: tuple[AlertUnsuccessfulToolCall, ...] = Field(min_length=1)


class AlertOccurrenceComparison(StrictAlertModel):
    """Arithmetic comparison between current and one reference occurrence total."""

    current: int = Field(ge=0)
    reference: int = Field(ge=0)
    delta: int
    direction: Literal["increased", "decreased", "unchanged"]


class AlertReferenceComparison(StrictAlertModel):
    """Configured reference offset and its successful occurrence comparison."""

    offset: str = Field(min_length=2)
    occurrence_comparison: AlertOccurrenceComparison


class AlertAgentCompletion(StrictAlertModel):
    """Strict final finding and importance output from the Alert agent."""

    findings: tuple[AlertFinding, ...]
    overall_importance: Literal["low", "moderate", "high", "critical"]

    @model_validator(mode="after")
    def ensure_unique_findings(self) -> AlertAgentCompletion:
        if len({finding.id for finding in self.findings}) != len(self.findings):
            raise ValueError("finding ids must be unique")
        return self


class AlertResultProvenance(StrictAlertModel):
    """Source and generation metadata for an Alert result artifact."""

    source_provider: str = Field(
        min_length=1,
        validation_alias=AliasChoices("source", "source_provider"),
        serialization_alias="source_provider",
    )
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return _utc(value)


class CompletedAlertAnalysisResult(StrictAlertModel):
    """Strict completed AlertAnalysisResult payload."""

    schema_version: Literal["1.0"] = "1.0"
    lens_type: Literal["alert"] = "alert"
    status: Literal["completed"] = "completed"
    identity: AlertIdentity
    analysis_timestamp: datetime
    analysis_window: AlertAnalysisWindow
    alerts: tuple[CanonicalAlertRecord, ...]
    alert_activity: AlertActivity
    status_distribution: AlertStatusDistribution
    duration_statistics: AlertDurationStatistics | None = None
    provider_importance_distribution: AlertProviderImportanceDistribution | None = None
    comparisons: tuple[AlertReferenceComparison, ...] = ()
    optional_tool_execution: AlertOptionalToolExecution | None = None
    findings: tuple[AlertFinding, ...]
    overall_importance: Literal["none", "low", "moderate", "high", "critical"]
    provenance: AlertResultProvenance

    @field_validator("analysis_timestamp")
    @classmethod
    def normalize_analysis_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_invariants(self) -> CompletedAlertAnalysisResult:
        if len({alert.id for alert in self.alerts}) != len(self.alerts):
            raise ValueError("current alert ids must be unique")
        if len(self.alerts) != self.alert_activity.record_count:
            raise ValueError("record_count must equal alerts length")
        effective_occurrences = sum(
            alert.occurrence_count if alert.occurrence_count is not None else 1
            for alert in self.alerts
        )
        if self.alert_activity.occurrence_count != effective_occurrences:
            raise ValueError("occurrence_count must equal effective alert occurrences")
        actual_statuses = {
            status: sum(alert.status.normalized == status for alert in self.alerts)
            for status in ("active", "resolved", "unknown")
        }
        if self.status_distribution.model_dump() != actual_statuses:
            raise ValueError("status distribution must equal alert statuses")
        if (
            sum(
                (
                    self.status_distribution.active,
                    self.status_distribution.resolved,
                    self.status_distribution.unknown,
                )
            )
            != self.alert_activity.record_count
        ):
            raise ValueError("status counts must equal record_count")
        for alert in self.alerts:
            if not isfinite(alert.duration_seconds):
                raise ValueError("alert duration must be finite")
            if alert.ended_at is not None and alert.ended_at < alert.started_at:
                raise ValueError("alert ended_at must not precede started_at")
            if alert.status.normalized == "active" and alert.ended_at is not None:
                raise ValueError("active alert must not have ended_at")
            if alert.status.normalized == "resolved" and alert.ended_at is None:
                raise ValueError("resolved alert requires ended_at")
            lifecycle_end = alert.ended_at or self.analysis_timestamp
            expected_duration = (lifecycle_end - alert.started_at).total_seconds()
            if alert.duration_seconds != expected_duration:
                raise ValueError("alert duration must match its lifecycle timestamps")
        if self.duration_statistics is not None:
            durations = [alert.duration_seconds for alert in self.alerts]
            expected_statistics = {
                "min_seconds": min(durations),
                "max_seconds": max(durations),
                "average_seconds": sum(durations) / len(durations),
            }
            if self.duration_statistics.model_dump() != expected_statistics:
                raise ValueError("duration statistics must equal alert durations")
        importance = [
            alert.provider_importance for alert in self.alerts if alert.provider_importance
        ]
        if self.provider_importance_distribution is not None:
            if not importance:
                raise ValueError("provider importance section requires provider importance")
            if any(item.type != self.provider_importance_distribution.type for item in importance):
                raise ValueError("provider importance type must match every alert")
            expected_values = {
                value: sum(item.value == value for item in importance)
                for value in {item.value for item in importance}
            }
            if self.provider_importance_distribution.values != expected_values:
                raise ValueError("provider importance values must equal alert importance")
        elif importance:
            raise ValueError("provider importance section is required when alerts have importance")
        for comparison in self.comparisons:
            occurrence = comparison.occurrence_comparison
            delta = occurrence.current - occurrence.reference
            direction = "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged"
            if occurrence.current != self.alert_activity.occurrence_count:
                raise ValueError("comparison current must equal current occurrence_count")
            if occurrence.delta != delta or occurrence.direction != direction:
                raise ValueError("comparison delta and direction must be exact")
        if self.alert_activity.record_count == 0:
            if (
                self.overall_importance != "none"
                or self.duration_statistics is not None
                or self.provider_importance_distribution is not None
            ):
                raise ValueError(
                    "zero-record result requires none importance and no optional aggregates"
                )
        elif self.overall_importance == "none" or self.duration_statistics is None:
            raise ValueError("non-zero result requires importance and duration statistics")
        return self


CompletedZeroAlertAnalysisResult = CompletedAlertAnalysisResult


class PartialAlertAnalysisResult(CompletedAlertAnalysisResult):
    """Usable Alert result carrying its single structured partial reason."""

    status: Literal["partial"] = "partial"
    reason: StructuredReason

    @model_validator(mode="after")
    def validate_partial_reason(self) -> PartialAlertAnalysisResult:
        if (self.reason.code, self.reason.component) not in {
            ("invalid_records", "current_normalization"),
            ("reference_unavailable", "reference_periods"),
        }:
            raise ValueError("unsupported Alert partial reason")
        return self


class AlertTerminalOutcome(StrictAlertModel):
    """ORM-neutral terminal status, reason, and optional artifact envelope."""

    status: Literal[LensRunStatus.COMPLETED, LensRunStatus.PARTIAL, LensRunStatus.FAILED] = (
        LensRunStatus.COMPLETED
    )
    reason: StructuredReason | None = None
    artifact: LensAnalysisResultInput | None = None

    @model_validator(mode="after")
    def correlate_partial_reason(self) -> AlertTerminalOutcome:
        if self.status is LensRunStatus.PARTIAL:
            if self.reason is None or self.artifact is None:
                raise ValueError(
                    "partial Alert outcome requires exactly one reason and an artifact"
                )
        elif self.status is LensRunStatus.COMPLETED:
            if self.reason is not None or self.artifact is None:
                raise ValueError("completed Alert outcome requires an artifact and no reason")
        elif self.reason is None or self.artifact is not None:
            raise ValueError("failed Alert outcome requires a reason and no artifact")
        return self
