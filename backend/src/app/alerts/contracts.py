"""Strict, framework-neutral contracts for the Alert analysis pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensRunStatus,
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

    from_: datetime = Field(alias="from")
    to: datetime

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


class AlertRecordsAvailable(StrictAlertModel):
    """Successful provider response; records are intentionally deferred past VS-01."""

    records: tuple[object, ...] = ()
    source: str = Field(min_length=1)


class AlertProviderUnavailable(StrictAlertModel):
    """Typed unavailable provider outcome reserved for a later failure slice."""

    state: Literal["unavailable"] = "unavailable"
    diagnostic: str = Field(min_length=1, max_length=512)


AlertProviderOutcome = AlertRecordsAvailable | AlertProviderUnavailable


class AlertMandatoryEvidence(StrictAlertModel):
    """The mandatory empty-data evidence produced before the zero gate."""

    record_count: Literal[0] = 0
    occurrence_count: Literal[0] = 0
    status_counts: dict[Literal["active", "resolved", "unknown"], Literal[0]] = Field(
        default_factory=lambda: {"active": 0, "resolved": 0, "unknown": 0}
    )


class AlertResultProvenance(StrictAlertModel):
    """Stable source provenance for a generated Alert artifact."""

    source: str = Field(min_length=1)
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return _utc(value)


class CompletedZeroAlertAnalysisResult(StrictAlertModel):
    """The only AlertAnalysisResult variant exercised by the empty walking skeleton."""

    schema_version: Literal["1.0"] = "1.0"
    lens_type: Literal["alert"] = "alert"
    status: Literal["completed"] = "completed"
    identity: AlertIdentity
    analysis_window: AlertAnalysisWindow
    activity: AlertMandatoryEvidence
    findings: tuple[()] = ()
    overall_importance: Literal["none"] = "none"
    provenance: AlertResultProvenance


class AlertTerminalOutcome(StrictAlertModel):
    """ORM-neutral terminal outcome ready for caller-owned transaction persistence."""

    status: Literal[LensRunStatus.COMPLETED] = LensRunStatus.COMPLETED
    reason: None = None
    artifact: LensAnalysisResultInput
