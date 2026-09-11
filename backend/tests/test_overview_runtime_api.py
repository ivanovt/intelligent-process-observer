"""HTTP tests for the resilient read-only Overview runtime boundary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx

from app.main import app
from app.observation_runs.contracts import ObservationRunObservation, ObservationRunSummary
from app.overview_runtime.api import get_overview_runtime_read_service
from app.overview_runtime.contracts import (
    OverviewRuntimeAvailable,
    OverviewRuntimeLimited,
    OverviewRuntimeResponse,
)


class StubOverviewRuntimeReadService:
    """Return configured Overview runtime data without any persistence mutation."""

    def __init__(self, result: OverviewRuntimeResponse | BaseException) -> None:
        self.result = result
        self.calls = 0

    async def get_runtime(self) -> OverviewRuntimeResponse:
        """Return the configured result and record one read operation."""

        self.calls += 1
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_overview_runtime_returns_mixed_items_and_is_side_effect_free() -> None:
    """Expose every independently projected item without invoking execution controls."""

    service = StubOverviewRuntimeReadService(_mixed_response())
    _override(service)
    try:
        first = _request("GET", "/api/v1/overview-runtime")
        second = _request("GET", "/api/v1/overview-runtime")
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    body = first.json()
    assert body["schema_version"] == "1.0"
    assert [item["availability"] for item in body["items"]] == ["available", "limited"]
    assert body["limited_run_count"] == 1
    assert "reason" not in body["items"][1]
    assert "analysis_window" not in body["items"][1]
    assert service.calls == 2


def test_overview_runtime_reports_empty_history_and_safe_persistence_failure() -> None:
    """Keep a true empty feed distinct from an unavailable runtime repository."""

    empty = StubOverviewRuntimeReadService(
        OverviewRuntimeResponse(schema_version="1.0", items=(), limited_run_count=0)
    )
    _override(empty)
    try:
        empty_response = _request("GET", "/api/v1/overview-runtime")
    finally:
        app.dependency_overrides.clear()
    unavailable = StubOverviewRuntimeReadService(RuntimeError("database unavailable"))
    _override(unavailable)
    try:
        unavailable_response = _request("GET", "/api/v1/overview-runtime")
    finally:
        app.dependency_overrides.clear()

    assert empty_response.status_code == 200
    assert empty_response.json() == {"schema_version": "1.0", "items": [], "limited_run_count": 0}
    assert unavailable_response.status_code == 503
    assert unavailable_response.json() == {
        "code": "runtime_read_unavailable",
        "message": "Run data is temporarily unavailable",
    }
    assert "database unavailable" not in unavailable_response.text


def _override(service: StubOverviewRuntimeReadService) -> None:
    async def dependency() -> StubOverviewRuntimeReadService:
        return service

    app.dependency_overrides[get_overview_runtime_read_service] = dependency


def _request(method: str, path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path)

    return asyncio.run(send())


def _mixed_response() -> OverviewRuntimeResponse:
    now = datetime(2026, 9, 10, 12, tzinfo=UTC)
    observation_id, available_id, limited_id = uuid4(), uuid4(), uuid4()
    observation = ObservationRunObservation(id=observation_id, name="Safe observation")
    return OverviewRuntimeResponse(
        schema_version="1.0",
        items=(
            OverviewRuntimeAvailable(
                availability="available",
                summary=ObservationRunSummary(
                    id=available_id,
                    observation=observation,
                    analysis_window={
                        "from": now - timedelta(hours=1),
                        "to": now,
                    },
                    status="completed",
                    reason=None,
                    analytical_state=None,
                    created_at=now,
                    started_at=now,
                    finished_at=now,
                    duration_seconds=0,
                    href=f"/api/v1/observation-runs/{available_id}",
                ),
            ),
            OverviewRuntimeLimited(
                availability="limited",
                id=limited_id,
                observation=observation,
                created_at=now - timedelta(minutes=1),
                status="failed",
                started_at=None,
                finished_at=None,
                duration_seconds=None,
                analytical_state=None,
                limitation_code="runtime_projection_invalid",
                href=f"/api/v1/observation-runs/{limited_id}",
            ),
        ),
        limited_run_count=1,
    )
