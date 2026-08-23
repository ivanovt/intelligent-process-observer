from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx

from app.main import app
from app.observations.api import get_service, get_session
from app.observations.contracts import MetricLensResponse, ObservationResponse, ObservationSummary
from app.observations.errors import ApiError


class StubObservationService:
    def __init__(self) -> None:
        self.observation_id = uuid4()
        self.lens = MetricLensResponse(
            id="coolant-temperature",
            name="Coolant temperature",
            description=None,
            type="metric",
            metric_id="coolant_temperature",
            adapter_type="prometheus",
            source_id="production-prometheus",
            query="avg(coolant_temperature_celsius)",
            unit="celsius",
            analysis_objectives=[],
            reference_periods=[],
            href=(f"/api/v1/observations/{self.observation_id}/lenses/coolant-temperature"),
            observation_href=f"/api/v1/observations/{self.observation_id}",
        )
        self.definition = ObservationResponse(
            id=self.observation_id,
            name="Cooling health",
            description=None,
            objective="Detect instability.",
            schema_version=1,
            lenses=[self.lens],
            relationships=[],
            href=f"/api/v1/observations/{self.observation_id}",
        )
        self.created_definition = None

    async def list(self, _session) -> list[ObservationSummary]:
        return [
            ObservationSummary(
                id=self.observation_id,
                name="Cooling health",
                description=None,
                objective="Detect instability.",
                schema_version=1,
                lenses=[],
                relationships=[],
                href=f"/api/v1/observations/{self.observation_id}",
            )
        ]

    async def get(self, _session, _observation_id):
        if _observation_id == self.observation_id:
            return self.definition
        raise ApiError(404, "observation_not_found", "Observation definition was not found")

    async def create(self, _session, definition):
        self.created_definition = definition
        return self.definition

    async def get_lens(self, _session, observation_id, lens_id):
        if observation_id == self.observation_id and lens_id == self.lens.id:
            return self.lens
        raise ApiError(404, "lens_not_found", "Lens definition was not found")


async def no_database_session() -> AsyncIterator[None]:
    yield None


def service_override(service: StubObservationService):
    async def get_stub_service() -> StubObservationService:
        return service

    return get_stub_service


def request(method: str, url: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(send())


def test_list_is_compact_and_unknown_resource_uses_machine_error_envelope() -> None:
    service = StubObservationService()
    app.dependency_overrides[get_service] = service_override(service)
    app.dependency_overrides[get_session] = no_database_session
    try:
        listed = request("GET", "/api/v1/observations")
        missing = request("GET", f"/api/v1/observations/{uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert listed.status_code == 200
    assert listed.json()[0]["href"] == f"/api/v1/observations/{service.observation_id}"
    assert missing.status_code == 404
    assert missing.json() == {
        "code": "observation_not_found",
        "message": "Observation definition was not found",
    }


def test_invalid_definition_uses_machine_readable_validation_error() -> None:
    service = StubObservationService()
    app.dependency_overrides[get_service] = service_override(service)
    app.dependency_overrides[get_session] = no_database_session
    try:
        response = request("POST", "/api/v1/observations", json={"name": ""})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["field"] == "name"


def test_create_and_follow_lens_link() -> None:
    service = StubObservationService()
    app.dependency_overrides[get_service] = service_override(service)
    app.dependency_overrides[get_session] = no_database_session
    payload = {
        "name": "Cooling health",
        "objective": "Detect instability.",
        "lenses": [
            {
                "id": "coolant-temperature",
                "name": "Coolant temperature",
                "type": "metric",
                "metric_id": "coolant_temperature",
                "adapter_type": "prometheus",
                "source_id": "production-prometheus",
                "query": "avg(coolant_temperature_celsius)",
                "unit": "celsius",
                "analysis_objectives": [],
                "reference_periods": [],
            }
        ],
        "relationships": [],
    }
    try:
        created = request("POST", "/api/v1/observations", json=payload)
        detail = request("GET", created.json()["href"])
        lens = request("GET", created.json()["lenses"][0]["href"])
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 201
    assert service.created_definition is not None
    assert detail.status_code == 200
    assert lens.status_code == 200
    assert lens.json()["observation_href"] == created.json()["href"]
