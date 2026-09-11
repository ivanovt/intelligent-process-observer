"""Safe per-record Overview projections over strict run-summary records."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError

from app.infrastructure.persistence.repository import ObservationRunSummaryRecord
from app.observation_runs.contracts import ObservationRunObservation
from app.observation_runs.projection import (
    RuntimeProjectionInvalid,
    project_observation_run_summary,
)
from app.overview_runtime.contracts import (
    OverviewRuntimeAvailable,
    OverviewRuntimeItem,
    OverviewRuntimeLimited,
    OverviewRuntimeResponse,
)


def project_overview_runtime_item(
    record: ObservationRunSummaryRecord, *, now: datetime | None = None
) -> OverviewRuntimeItem:
    """Return one strict summary or a whitelisted limited projection for that record."""

    try:
        return OverviewRuntimeAvailable(
            availability="available",
            summary=project_observation_run_summary(record, now=now),
        )
    except RuntimeProjectionInvalid:
        return _limited_item(record, now=now)


def project_overview_runtime_response(
    records: list[ObservationRunSummaryRecord], *, now: datetime | None = None
) -> OverviewRuntimeResponse:
    """Project ordered records independently without concealing valid neighbours."""

    items = tuple(project_overview_runtime_item(record, now=now) for record in records)
    try:
        return OverviewRuntimeResponse(
            schema_version="1.0",
            items=items,
            limited_run_count=sum(item.availability == "limited" for item in items),
        )
    except (TypeError, ValueError, ValidationError) as error:
        raise RuntimeProjectionInvalid("Overview runtime projection is invalid") from error


def _limited_item(
    record: ObservationRunSummaryRecord, *, now: datetime | None
) -> OverviewRuntimeLimited:
    """Whitelist independently valid parent lifecycle values and nothing analytical."""

    run = record.observation_run
    created_at = _required_utc_timestamp(run.created_at, "Run creation timestamp is invalid")
    started_at = _optional_utc_timestamp(run.started_at)
    finished_at = _optional_utc_timestamp(run.finished_at)
    try:
        return OverviewRuntimeLimited(
            availability="limited",
            id=run.id,
            observation=ObservationRunObservation(
                id=run.observation_id, name=record.observation_name
            ),
            created_at=created_at,
            status=_optional_status(run.status),
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=_optional_duration(started_at, finished_at, now=now),
            analytical_state=None,
            limitation_code="runtime_projection_invalid",
            href=f"/api/v1/observation-runs/{run.id}",
        )
    except (TypeError, ValueError, ValidationError) as error:
        raise RuntimeProjectionInvalid("Overview runtime projection is invalid") from error


def _required_utc_timestamp(value: object, message: str) -> datetime:
    """Return a required exact UTC timestamp or preserve the fail-closed boundary."""

    timestamp = _optional_utc_timestamp(value)
    if timestamp is None:
        raise RuntimeProjectionInvalid(message)
    return timestamp


def _optional_utc_timestamp(value: object) -> datetime | None:
    """Admit a lifecycle timestamp only when it is independently an exact UTC datetime."""

    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    if value.utcoffset() != UTC.utcoffset(value):
        return None
    return value.astimezone(UTC)


def _optional_status(value: object) -> str | None:
    """Admit only exact public ObservationRun lifecycle statuses."""

    if value in {"pending", "running", "completed", "failed", "cancelled"}:
        return value
    return None


def _optional_duration(
    started_at: datetime | None, finished_at: datetime | None, *, now: datetime | None
) -> float | None:
    """Derive duration only from independently valid chronological timestamps."""

    if started_at is None:
        return None
    end = finished_at if finished_at is not None else now or datetime.now(UTC)
    seconds = (end - started_at).total_seconds()
    return seconds if seconds >= 0 else None
