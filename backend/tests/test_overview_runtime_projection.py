"""Focused tests for the resilient, public-safe Overview runtime projection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.infrastructure.persistence.models import ObservationRunModel
from app.infrastructure.persistence.repository import ObservationRunSummaryRecord
from app.overview_runtime.contracts import OverviewRuntimeLimited, OverviewRuntimeResponse
from app.overview_runtime.projection import (
    project_overview_runtime_item,
    project_overview_runtime_response,
)


def test_response_contract_requires_exact_limited_count_and_forbids_extra_data() -> None:
    """Keep coverage accounting and public field whitelists strict at the wire boundary."""

    limited = _limited_model()
    response = OverviewRuntimeResponse(schema_version="1.0", items=(limited,), limited_run_count=1)

    assert response.limited_run_count == 1
    with pytest.raises(ValidationError):
        OverviewRuntimeResponse(schema_version="1.0", items=(limited,), limited_run_count=0)
    with pytest.raises(ValidationError):
        OverviewRuntimeLimited.model_validate(
            {**limited.model_dump(), "execution_context": {"secret": "never public"}}
        )


def test_limited_contract_validates_optional_lifecycle_fields_independently() -> None:
    """Preserve safe timestamps while leaving invalid status and duration unavailable."""

    created = datetime(2026, 9, 10, 12, tzinfo=UTC)
    run = _run(created)
    run.execution_context = {"private": "invalid strict context"}
    run.status = "legacy-status"
    run.started_at = datetime(2026, 9, 10, 11)
    run.finished_at = created

    item = project_overview_runtime_item(_record(run), now=created + timedelta(minutes=1))

    assert item.availability == "limited"
    assert item.status is None
    assert item.started_at is None
    assert item.finished_at == created
    assert item.duration_seconds is None
    assert item.analytical_state is None


def test_projection_keeps_mixed_records_ordered_and_never_leaks_invalid_content() -> None:
    """Make one invalid analysis window limited without concealing neighbouring summaries."""

    now = datetime(2026, 9, 10, 12, tzinfo=UTC)
    newest_valid = _run(now)
    legacy = _run(now - timedelta(minutes=1))
    legacy.execution_context = {
        "analysis_window": {"from": (now - timedelta(hours=1)).isoformat()},
        "provider_payload": {"token": "TOP-SECRET"},
    }
    oldest_valid = _run(now - timedelta(minutes=2))

    response = project_overview_runtime_response(
        [_record(newest_valid), _record(legacy), _record(oldest_valid)], now=now
    )

    assert [item.availability for item in response.items] == ["available", "limited", "available"]
    assert response.limited_run_count == 1
    limited = response.items[1]
    serialized = limited.model_dump_json()
    assert "analysis_window" not in serialized
    assert "provider_payload" not in serialized
    assert "TOP-SECRET" not in serialized
    assert "reason" not in serialized
    assert "diagnostic" not in serialized


def _limited_model() -> OverviewRuntimeLimited:
    now = datetime(2026, 9, 10, 12, tzinfo=UTC)
    run = _run(now)
    run.execution_context = {}
    item = project_overview_runtime_item(_record(run), now=now)
    assert isinstance(item, OverviewRuntimeLimited)
    return item


def _record(run: ObservationRunModel) -> ObservationRunSummaryRecord:
    return ObservationRunSummaryRecord(
        observation_run=run,
        observation_name="Safe observation",
        analysis_schema_version=None,
        analysis_payload=None,
    )


def _run(created_at: datetime) -> ObservationRunModel:
    return ObservationRunModel(
        id=uuid4(),
        observation_id=uuid4(),
        status="running",
        reason={"code": "private_diagnostic", "component": "executor"},
        provenance={"token": "TOP-SECRET"},
        execution_context={
            "analysis_window": {
                "from": (created_at - timedelta(hours=1)).isoformat(),
                "to": created_at.isoformat(),
            }
        },
        created_at=created_at,
        started_at=created_at,
    )
