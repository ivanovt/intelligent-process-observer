"""Strict, framework-neutral contracts for the Alert analysis pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensRunStatus,
    StructuredReason,
)


class StrictAlertModel(BaseModel):
    """Reject undeclared fields on immutable Alert pipeline values."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


class AlertIdentity(StrictAlertModel):
    """Runtime identity inherited from one existing LensRun."""

    observation_id: UUID
    observation_run_id: UUID
    lens_id: str = Field(min_length=1)
    lens_run_id: UUID


class AlertAnalysisWindow(StrictAlertModel):
    """The fixed time boundary for one Alert acquisition."""

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
    """Opaque, frozen provider inputs derived from an Alert Lens definition."""

    source: str = Field(min_length=1)
    query: str = Field(min_length=1)


class AlertLensExecutionContext(StrictAlertModel):
    """Immutable scope for analyzing one already-running Alert LensRun."""

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
    """Provider-native importance retained without cross-provider mapping."""

    type: str = Field(min_length=1)
    value: str = Field(min_length=1)


class AlertProviderRecord(StrictAlertModel):
    """Provider-mapped record awaiting canonical lifecycle normalization."""

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
    """Successful provider response with mapped records only."""

    # Provider mapping can leave malformed values for application-owned normalization.
    records: tuple[AlertProviderRecord | dict[str, Any], ...] = ()
    source: str = Field(min_length=1)


class AlertProviderUnavailable(StrictAlertModel):
    """Typed unavailable provider outcome reserved for a later failure slice."""

    state: Literal["unavailable"] = "unavailable"
    diagnostic: str = Field(min_length=1, max_length=512)


class AlertProviderFailure(StrictAlertModel):
    """Typed non-timeout failure from a provider acquisition attempt."""

    state: Literal["failed"] = "failed"
    diagnostic: str = Field(min_length=1, max_length=512)


class AlertProviderTimeout(StrictAlertModel):
    """Typed timeout from a provider acquisition attempt."""

    state: Literal["timeout"] = "timeout"
    diagnostic: str = Field(min_length=1, max_length=512)


AlertProviderOutcome = (
    AlertRecordsAvailable | AlertProviderUnavailable | AlertProviderFailure | AlertProviderTimeout
)


class AlertStatus(StrictAlertModel):
    """Canonical and source lifecycle status for one normalized Alert."""

    normalized: Literal["active", "resolved", "unknown"]
    source: str = Field(min_length=1)


class CanonicalAlertRecord(StrictAlertModel):
    """Validated current Alert record used for evidence and result projection."""

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
    """Top-level count evidence for current normalized alerts."""

    record_count: int = Field(ge=0)
    occurrence_count: int = Field(ge=0)


class AlertStatusDistribution(StrictAlertModel):
    """Top-level record-based status counts for current alerts."""

    active: int = Field(ge=0)
    resolved: int = Field(ge=0)
    unknown: int = Field(ge=0)


class AlertDurationStatistics(StrictAlertModel):
    """Finite full-lifecycle duration statistics in seconds."""

    min_seconds: float = Field(ge=0, allow_inf_nan=False)
    max_seconds: float = Field(ge=0, allow_inf_nan=False)
    average_seconds: float = Field(ge=0, allow_inf_nan=False)


class AlertProviderImportanceDistribution(StrictAlertModel):
    """Grouped native provider importance values of one declared type."""

    type: str = Field(min_length=1)
    values: dict[str, int] = Field(min_length=1)


class AlertMandatoryEvidence(StrictAlertModel):
    """Deterministic mandatory evidence formed before the Alert agent gate."""

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
    """A Lens-local agent finding grounded in persisted Alert evidence."""

    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_refs: tuple[str, ...]


class AlertAgentRequest(StrictAlertModel):
    """Exact bounded source-agnostic projection supplied to the Alert agent."""

    lens_name: str = Field(min_length=1)
    lens_description: str | None = None
    current_records: tuple[CanonicalAlertRecord, ...]
    mandatory_evidence: AlertMandatoryEvidence
    comparisons: tuple[AlertReferenceComparison, ...] = ()


class AlertOccurrenceComparison(StrictAlertModel):
    """Current occurrence activity relative to one successful reference period."""

    current: int = Field(ge=0)
    reference: int = Field(ge=0)
    delta: int
    direction: Literal["increased", "decreased", "unchanged"]


class AlertReferenceComparison(StrictAlertModel):
    """Compact evidence retained for one successful configured reference offset."""

    offset: str = Field(min_length=2)
    occurrence_comparison: AlertOccurrenceComparison


class AlertAgentCompletion(StrictAlertModel):
    """Strict bounded reasoning output returned before result construction."""

    findings: tuple[AlertFinding, ...]
    overall_importance: Literal["low", "moderate", "high", "critical"]

    @model_validator(mode="after")
    def ensure_unique_findings(self) -> AlertAgentCompletion:
        if len({finding.id for finding in self.findings}) != len(self.findings):
            raise ValueError("finding ids must be unique")
        return self


class AlertResultProvenance(StrictAlertModel):
    """Stable source provenance for a generated Alert artifact."""

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
    """Strict completed Alert 1.0 artifact for current valid records."""

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
    findings: tuple[AlertFinding, ...]
    overall_importance: Literal["none", "low", "moderate", "high", "critical"]
    provenance: AlertResultProvenance

    @field_validator("analysis_timestamp")
    @classmethod
    def normalize_analysis_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_invariants(self) -> CompletedAlertAnalysisResult:
        if len(self.alerts) != self.alert_activity.record_count:
            raise ValueError("record_count must equal alerts length")
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
        if self.alert_activity.record_count == 0:
            if self.overall_importance != "none" or self.duration_statistics is not None:
                raise ValueError(
                    "zero-record result requires none importance and no duration statistics"
                )
        elif self.overall_importance == "none" or self.duration_statistics is None:
            raise ValueError("non-zero result requires importance and duration statistics")
        return self


CompletedZeroAlertAnalysisResult = CompletedAlertAnalysisResult


class PartialAlertAnalysisResult(CompletedAlertAnalysisResult):
    """Strict usable Alert artifact with one approved incompleteness reason."""

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
    """ORM-neutral terminal outcome ready for caller-owned transaction persistence."""

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
