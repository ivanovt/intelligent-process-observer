"""Focused HTTP tests for the public managed Observation run boundary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from app.core.settings import Settings
from app.execution import (
    AnalysisWindow,
    ExecutionReason,
    LaunchAccepted,
    LaunchConflict,
    LaunchUnavailable,
    ObservationRunAcceptanceSummary,
    RejectedObservationExecutionOutcome,
)
from app.main import app
from app.observation_runs.api import get_run_manager, get_run_read_service
from app.observation_runs.contracts import ObservationRunSummary
from app.observation_runs.projection import RuntimeProjectionInvalid


class StubRunManager:
    """Record one API launch and return a configured manager outcome."""

    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.requests = []

    async def launch(self, request: object) -> object:
        """Capture the framework-neutral request without performing persistence."""

        self.requests.append(request)
        return self.outcome


class StubRunReadService:
    """Provide fixed detached read projections without mutating runtime state."""

    def __init__(
        self,
        *,
        summaries: tuple[ObservationRunSummary, ...] = (),
        detail: object | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.summaries = summaries
        self.detail = detail
        self.error = error
        self.list_calls = 0
        self.detail_calls: list[UUID] = []

    async def list_summaries(self) -> tuple[ObservationRunSummary, ...]:
        """Return the configured history without a write operation."""

        self.list_calls += 1
        if self.error is not None:
            raise self.error
        return self.summaries

    async def get_detail(self, observation_run_id: UUID) -> object | None:
        """Return the configured detail without a write operation."""

        self.detail_calls.append(observation_run_id)
        if self.error is not None:
            raise self.error
        return self.detail


def _accepted() -> LaunchAccepted:
    now = datetime.now(UTC)
    observation_id, run_id = uuid4(), uuid4()
    return LaunchAccepted(
        ObservationRunAcceptanceSummary(
            observation_run_id=run_id,
            observation_id=observation_id,
            observation_name="Cooling health",
            analysis_window=AnalysisWindow(now - timedelta(minutes=5), now),
            created_at=now,
            started_at=now,
            href=f"/api/v1/observation-runs/{run_id}",
        )
    )


def _request(method: str, path: str, **kwargs: object) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def _override(manager: StubRunManager, reader: StubRunReadService) -> None:
    async def manager_dependency() -> StubRunManager:
        return manager

    async def reader_dependency() -> StubRunReadService:
        return reader

    app.dependency_overrides[get_run_manager] = manager_dependency
    app.dependency_overrides[get_run_read_service] = reader_dependency


def _payload(observation_id: UUID) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "observation_id": str(observation_id),
        "analysis_window": {
            "from": (now - timedelta(minutes=5)).isoformat(),
            "to": now.isoformat(),
        },
    }


def _json_timestamp(value: datetime) -> str:
    """Mirror FastAPI's canonical UTC JSON serialization in exact response assertions."""

    return value.isoformat().replace("+00:00", "Z")


def test_launch_returns_only_its_captured_running_acceptance_summary() -> None:
    accepted = _accepted()
    manager = StubRunManager(accepted)
    reader = StubRunReadService()
    _override(manager, reader)
    try:
        response = _request(
            "POST", "/api/v1/observation-runs", json=_payload(accepted.summary.observation_id)
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json() == {
        "id": str(accepted.summary.observation_run_id),
        "observation": {"id": str(accepted.summary.observation_id), "name": "Cooling health"},
        "analysis_window": {
            "from": _json_timestamp(accepted.summary.analysis_window.from_),
            "to": _json_timestamp(accepted.summary.analysis_window.to),
        },
        "status": "running",
        "reason": None,
        "analytical_state": None,
        "created_at": _json_timestamp(accepted.summary.created_at),
        "started_at": _json_timestamp(accepted.summary.started_at),
        "finished_at": None,
        "duration_seconds": None,
        "href": accepted.summary.href,
    }
    assert len(manager.requests) == 1
    assert reader.list_calls == 0
    assert reader.detail_calls == []


@pytest.mark.parametrize(
    "patch",
    [
        {"analysis_window": {"from": "2026-09-09T12:00:00Z", "to": "2026-09-09T12:00:00Z"}},
        {"analysis_window": {"from": "2026-09-09T11:00:00", "to": "2026-09-09T12:00:00Z"}},
        {"model": "client-controlled"},
    ],
)
def test_launch_validation_rejects_invalid_or_undeclared_input_before_manager(
    patch: dict[str, object],
) -> None:
    manager, reader = StubRunManager(_accepted()), StubRunReadService()
    payload = _payload(uuid4())
    payload.update(patch)
    _override(manager, reader)
    try:
        response = _request("POST", "/api/v1/observation-runs", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert manager.requests == []


@pytest.mark.parametrize(
    ("outcome", "status_code", "code"),
    [
        (LaunchConflict(uuid4()), 409, "observation_run_active"),
        (LaunchUnavailable(), 503, "execution_recovery_pending"),
        (LaunchUnavailable("launch_admission_uncertain"), 503, "launch_admission_uncertain"),
        (
            RejectedObservationExecutionOutcome(
                ExecutionReason("observation_not_found", "execution_preparation")
            ),
            404,
            "observation_not_found",
        ),
        (
            RejectedObservationExecutionOutcome(
                ExecutionReason("unsupported_lens_type", "execution_preparation")
            ),
            422,
            "unsupported_lens_type",
        ),
        (
            RejectedObservationExecutionOutcome(
                ExecutionReason("invalid_observation_definition", "execution_preparation")
            ),
            422,
            "invalid_observation_definition",
        ),
        (
            RejectedObservationExecutionOutcome(
                ExecutionReason("empty_lens_topology", "execution_preparation")
            ),
            422,
            "empty_lens_topology",
        ),
    ],
)
def test_launch_maps_only_safe_manager_outcomes(
    outcome: object, status_code: int, code: str
) -> None:
    manager, reader = StubRunManager(outcome), StubRunReadService()
    _override(manager, reader)
    try:
        response = _request("POST", "/api/v1/observation-runs", json=_payload(uuid4()))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == status_code
    assert response.json()["code"] == code
    assert "Traceback" not in response.text
    if isinstance(outcome, LaunchConflict):
        assert response.json()["observation_run_id"] == str(outcome.observation_run_id)
        assert response.json()["href"] == f"/api/v1/observation-runs/{outcome.observation_run_id}"


def test_run_reads_are_side_effect_free_and_fail_closed() -> None:
    accepted = _accepted()
    summary = ObservationRunSummary.model_validate(
        {
            "id": accepted.summary.observation_run_id,
            "observation": {
                "id": accepted.summary.observation_id,
                "name": accepted.summary.observation_name,
            },
            "analysis_window": {
                "from": accepted.summary.analysis_window.from_,
                "to": accepted.summary.analysis_window.to,
            },
            "status": "running",
            "reason": None,
            "analytical_state": None,
            "created_at": accepted.summary.created_at,
            "started_at": accepted.summary.started_at,
            "finished_at": None,
            "duration_seconds": None,
            "href": accepted.summary.href,
        }
    )
    manager, reader = StubRunManager(accepted), StubRunReadService(summaries=(summary,))
    _override(manager, reader)
    try:
        listed = _request("GET", "/api/v1/observation-runs")
        missing = _request("GET", f"/api/v1/observation-runs/{uuid4()}")
        reader.error = RuntimeProjectionInvalid("sentinel diagnostic")
        invalid = _request("GET", f"/api/v1/observation-runs/{summary.id}")
    finally:
        app.dependency_overrides.clear()

    assert listed.status_code == 200
    assert listed.json()[0]["id"] == str(summary.id)
    assert missing.status_code == 404
    assert missing.json()["code"] == "observation_run_not_found"
    assert invalid.status_code == 500
    assert invalid.json() == {
        "code": "runtime_projection_invalid",
        "message": "Run projection is unavailable",
    }
    assert manager.requests == []
    assert reader.list_calls == 1
    assert len(reader.detail_calls) == 2


def test_run_launch_is_unauthenticated_without_enabling_cross_origin_access() -> None:
    """Keep ADR-170's trusted boundary free of identity and permissive CORS behavior."""

    accepted = _accepted()
    manager, reader = StubRunManager(accepted), StubRunReadService()
    _override(manager, reader)
    try:
        response = _request(
            "POST",
            "/api/v1/observation-runs",
            json=_payload(accepted.summary.observation_id),
            headers={"Origin": "https://untrusted.example.test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert "access-control-allow-origin" not in response.headers
    assert "authorization" not in response.request.headers


def test_lifespan_composes_manager_and_completes_detached_work_with_injected_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the API through its lifespan-owned manager with deterministic components."""

    import app.main as main_module

    class _Engine:
        async def dispose(self) -> None:
            return None

    class _StateStore:
        async def reconcile_active_observation_runs(self) -> None:
            return None

        async def has_active_observation_runs(self) -> bool:
            return False

        async def get_active_observation_run_id(self, _observation_id: UUID) -> UUID | None:
            return None

    class _Orchestrator:
        def __init__(self) -> None:
            self.continued = asyncio.Event()

        async def initialize(self, request, _policy):
            now = datetime.now(UTC)
            run_id = uuid4()
            return SimpleNamespace(
                observation_run_id=run_id,
                acceptance_summary=ObservationRunAcceptanceSummary(
                    observation_run_id=run_id,
                    observation_id=request.observation_id,
                    observation_name="Injected Observation",
                    analysis_window=request.analysis_window,
                    created_at=now,
                    started_at=now,
                    href=f"/api/v1/observation-runs/{run_id}",
                ),
            )

        async def continue_execution(self, _initialized, _policy) -> object:
            self.continued.set()
            return SimpleNamespace(kind="completed")

    orchestrator = _Orchestrator()
    monkeypatch.setattr(main_module, "get_settings", lambda: Settings())
    monkeypatch.setattr(main_module, "create_database_engine", lambda: _Engine())
    monkeypatch.setattr(main_module, "create_session_factory", lambda _engine: object())
    monkeypatch.setattr(main_module, "RuntimeExecutionStateStore", lambda *_args: _StateStore())
    monkeypatch.setattr(
        main_module,
        "build_production_execution_composition",
        lambda **_kwargs: SimpleNamespace(orchestrator=orchestrator),
    )

    async def exercise() -> None:
        async with main_module.lifespan(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/observation-runs", json=_payload(uuid4()))
            assert response.status_code == 202
            assert response.json()["status"] == "running"
            await orchestrator.continued.wait()

    asyncio.run(exercise())
