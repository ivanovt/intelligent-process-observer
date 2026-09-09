"""Strict public response contracts for Observation run reads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.alerts.contracts import CompletedAlertAnalysisResult, PartialAlertAnalysisResult
from app.infrastructure.persistence.runtime_contracts import StructuredReason
from app.metrics.contracts import (
    CompletedInsufficientMetricResult,
    CompletedSufficientMetricResult,
    FailedMetricResult,
    PartialMetricResult,
)
from app.reasoning.contracts import ObservationAnalysisResult
from app.relationships.contracts import RelationshipEvaluation
from app.reporting.contracts import ObservationReport


class StrictObservationRunResponse(BaseModel):
    """Base public response model that accepts only declared safe fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ObservationRunObservation(StrictObservationRunResponse):
    """The sole Observation identity and display data shown by a run."""

    id: UUID
    name: str = Field(min_length=1)


class ObservationRunAnalysisWindow(StrictObservationRunResponse):
    """The immutable UTC interval selected for one run."""

    from_: datetime = Field(alias="from")
    to: datetime

    @field_validator("from_", "to")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        """Require exact aware UTC values before they cross the public boundary."""

        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("analysis window timestamps must be UTC")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_forward_window(self) -> ObservationRunAnalysisWindow:
        """Keep the public interval consistent with execution initialization."""

        if self.from_ >= self.to:
            raise ValueError("analysis window must be forward")
        return self


class ObservationRunSummary(StrictObservationRunResponse):
    """Compact immutable lifecycle projection shared by launch and history reads."""

    id: UUID
    observation: ObservationRunObservation
    analysis_window: ObservationRunAnalysisWindow
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    reason: StructuredReason | None
    analytical_state: (
        Literal["no_significant_findings", "uncertain", "significant_findings_present"] | None
    )
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None = Field(default=None, ge=0)
    href: str = Field(min_length=1)

    @field_validator("created_at", "started_at", "finished_at")
    @classmethod
    def require_utc_timestamps(cls, value: datetime | None) -> datetime | None:
        """Reject naive or non-UTC durable lifecycle timestamps."""

        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("lifecycle timestamps must be UTC")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def correlate_lifecycle(self) -> ObservationRunSummary:
        """Reject contradictory lifecycle timestamps and canonical links."""

        if self.href != f"/api/v1/observation-runs/{self.id}":
            raise ValueError("run detail href is not canonical")
        if self.finished_at is not None and self.started_at is None:
            raise ValueError("finished run requires a start timestamp")
        if self.started_at is not None and self.finished_at is not None:
            if self.finished_at < self.started_at:
                raise ValueError("finished_at cannot precede started_at")
        return self


MetricLensRunResult = (
    CompletedSufficientMetricResult
    | CompletedInsufficientMetricResult
    | PartialMetricResult
    | FailedMetricResult
)
AlertLensRunResult = CompletedAlertAnalysisResult | PartialAlertAnalysisResult
LensRunResult = MetricLensRunResult | AlertLensRunResult


class ObservationRunLensRun(StrictObservationRunResponse):
    """Whitelisted lifecycle wrapper around one exact Lens artifact union."""

    id: UUID
    lens_id: str = Field(min_length=1)
    lens_type: Literal["metric", "alert"]
    status: Literal["pending", "running", "completed", "partial", "failed", "cancelled"]
    reason: StructuredReason | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None = Field(default=None, ge=0)
    result: LensRunResult | None

    @field_validator("started_at", "finished_at")
    @classmethod
    def require_utc_timestamps(cls, value: datetime | None) -> datetime | None:
        """Reject naive or non-UTC durable Lens lifecycle timestamps."""

        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("Lens lifecycle timestamps must be UTC")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def correlate_lifecycle(self) -> ObservationRunLensRun:
        """Keep terminal timing and exact artifact type separate but consistent."""

        if self.finished_at is not None and self.started_at is None:
            raise ValueError("finished LensRun requires a start timestamp")
        if self.started_at is not None and self.finished_at is not None:
            if self.finished_at < self.started_at:
                raise ValueError("LensRun finished_at cannot precede started_at")
        if self.result is not None and self.result.lens_type != self.lens_type:
            raise ValueError("Lens result type contradicts LensRun")
        return self


class ObservationRunDetail(StrictObservationRunResponse):
    """One coherent run snapshot with all currently persisted public artifacts."""

    summary: ObservationRunSummary
    lens_runs: tuple[ObservationRunLensRun, ...]
    relationship_evaluations: tuple[RelationshipEvaluation, ...]
    analysis: ObservationAnalysisResult | None
    report: ObservationReport | None
