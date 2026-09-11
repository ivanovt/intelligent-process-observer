"""Strict public response contracts for resilient Overview runtime reads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.observation_runs.contracts import (
    ObservationRunObservation,
    ObservationRunSummary,
    StrictObservationRunResponse,
)


class OverviewRuntimeAvailable(StrictObservationRunResponse):
    """One complete strict run summary admitted to the Overview feed."""

    availability: Literal["available"]
    summary: ObservationRunSummary


class OverviewRuntimeLimited(StrictObservationRunResponse):
    """A minimal safe run projection when the complete summary is invalid."""

    availability: Literal["limited"]
    id: UUID
    observation: ObservationRunObservation
    created_at: datetime
    status: Literal["pending", "running", "completed", "failed", "cancelled"] | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None = Field(default=None, ge=0)
    analytical_state: None = None
    limitation_code: Literal["runtime_projection_invalid"]
    href: str = Field(min_length=1)

    @field_validator("created_at", "started_at", "finished_at")
    @classmethod
    def require_utc_timestamps(cls, value: datetime | None) -> datetime | None:
        """Reject naive or non-UTC lifecycle timestamps at the public boundary."""

        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("lifecycle timestamps must be UTC")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_canonical_href(self) -> OverviewRuntimeLimited:
        """Keep the optional strict-detail link anchored to this stable run identity."""

        if self.href != f"/api/v1/observation-runs/{self.id}":
            raise ValueError("run detail href is not canonical")
        return self


OverviewRuntimeItem = Annotated[
    OverviewRuntimeAvailable | OverviewRuntimeLimited,
    Field(discriminator="availability"),
]


class OverviewRuntimeResponse(StrictObservationRunResponse):
    """One ordered resilient runtime feed with explicit limited-item coverage."""

    schema_version: Literal["1.0"]
    items: tuple[OverviewRuntimeItem, ...]
    limited_run_count: int = Field(ge=0)

    @model_validator(mode="after")
    def require_exact_limited_count(self) -> OverviewRuntimeResponse:
        """Require the coverage count to match the returned discriminated items."""

        if self.limited_run_count != sum(item.availability == "limited" for item in self.items):
            raise ValueError("limited_run_count must match limited items")
        return self
