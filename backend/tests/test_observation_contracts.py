from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.settings import BearerTokenCredentials, PrometheusSourceSettings, Settings
from app.infrastructure.persistence.repository import ObservationRepository
from app.infrastructure.prometheus.contracts import (
    PrometheusRangeQueryResult,
    PrometheusRangeSample,
    PrometheusRangeSeries,
)
from app.observations.contracts import MetricPreflightRequest, ObservationCreate
from app.observations.service import ObservationDefinitionService


def valid_definition() -> dict:
    return {
        "name": "Cooling health",
        "objective": "Detect cooling-system instability.",
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
                "analysis_objectives": ["spike", "drift"],
                "reference_periods": ["60m"],
            },
            {
                "id": "coolant-pressure",
                "name": "Coolant pressure",
                "type": "metric",
                "metric_id": "coolant_pressure",
                "adapter_type": "prometheus",
                "source_id": "production-prometheus",
                "query": "avg(coolant_pressure_bar)",
                "unit": "bar",
                "analysis_objectives": [],
                "reference_periods": [],
            },
        ],
        "relationships": [
            {
                "id": "temperature-pressure-link",
                "name": "Temperature and pressure",
                "participants": ["coolant-temperature", "coolant-pressure"],
                "conditions": {},
                "expected": {
                    "coolant-temperature": {"trend": {"direction": "increasing"}},
                    "coolant-pressure": {"variability": {"state": "low"}},
                },
            }
        ],
    }


def configured_settings() -> Settings:
    return Settings(
        prometheus_sources=[
            PrometheusSourceSettings(
                id="production-prometheus",
                name="Production Prometheus",
                base_url="https://prometheus.example.test",
                credentials=BearerTokenCredentials(type="bearer_token", token="secret"),
            )
        ]
    )


def test_definition_contract_accepts_metric_topology() -> None:
    definition = ObservationCreate.model_validate(valid_definition())

    assert [lens.id for lens in definition.lenses] == [
        "coolant-temperature",
        "coolant-pressure",
    ]
    assert definition.relationships[0].conditions == {}


class RecordingSession:
    def __init__(self) -> None:
        self.added: object | None = None

    def add(self, value: object) -> None:
        self.added = value

    async def flush(self) -> None:
        return None

    async def refresh(self, value: object, *, attribute_names: list[str]) -> None:
        return None


def test_repository_builds_one_owned_aggregate() -> None:
    session = RecordingSession()
    definition = ObservationCreate.model_validate(valid_definition())

    aggregate = asyncio.run(ObservationRepository().create(session, definition))

    assert session.added is aggregate
    assert [lens.lens_id for lens in aggregate.lenses] == [
        "coolant-temperature",
        "coolant-pressure",
    ]
    assert aggregate.relationships[0].participants == ["coolant-temperature", "coolant-pressure"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda definition: definition["lenses"][0].update(id="not valid"),
        lambda definition: definition["lenses"][0].update(analysis_objectives=["spike", "spike"]),
        lambda definition: definition["lenses"][0].update(reference_periods=["0m"]),
        lambda definition: definition["relationships"][0].update(
            participants=["coolant-temperature", "coolant-temperature"]
        ),  # type: ignore[index]
        lambda definition: definition["relationships"][0].update(
            expected={"coolant-temperature": {"trend": {"direction": "unknown"}}}
        ),  # type: ignore[index]
    ],
)
def test_definition_contract_rejects_invalid_topology_or_vocabulary(mutate) -> None:
    definition = valid_definition()
    mutate(definition)

    with pytest.raises(ValidationError):
        ObservationCreate.model_validate(definition)


def test_capabilities_and_relative_hrefs_do_not_expose_connection_details(monkeypatch) -> None:
    import app.observations.service as service_module

    monkeypatch.setattr(service_module, "get_settings", configured_settings)
    service = ObservationDefinitionService()
    capabilities = service.capabilities()
    assert capabilities.model_dump() == {
        "metric": [
            {
                "adapter_type": "prometheus",
                "sources": [{"id": "production-prometheus", "name": "Production Prometheus"}],
            }
        ]
    }

    observation = SimpleNamespace(
        id=uuid4(),
        name="Cooling health",
        description=None,
        objective="Detect instability.",
        schema_version=1,
        lenses=[],
        alert_lenses=[],
        relationships=[],
    )
    summary = service.observation_summary(observation)
    assert summary.href == f"/api/v1/observations/{observation.id}"


def test_alert_contract_defaults_and_ignores_unknown_fields() -> None:
    definition = ObservationCreate.model_validate(
        {
            "name": "Release health",
            "objective": "Observe release alerts.",
            "alert_lenses": [
                {
                    "id": "release-alerts",
                    "type": "alert",
                    "name": "Release alerts",
                    "source": "jira_track_and_release",
                    "selector": {"query": "project = REL", "future_selector": "ignored"},
                    "future_alert_field": {"ignored": True},
                }
            ],
        }
    )

    alert = definition.alert_lenses[0]
    assert definition.lenses == []
    assert definition.relationships == []
    assert alert.description is None
    assert alert.analysis_objectives == []
    assert alert.reference_periods == []
    assert alert.model_dump() == {
        "id": "release-alerts",
        "name": "Release alerts",
        "description": None,
        "type": "alert",
        "source": "jira_track_and_release",
        "selector": {"query": "project = REL"},
        "analysis_objectives": [],
        "reference_periods": [],
    }


@pytest.mark.parametrize("payload", [{}, {"lenses": [], "alert_lenses": []}])
def test_definition_contract_requires_one_lens_across_type_specific_collections(payload) -> None:
    with pytest.raises(ValidationError):
        ObservationCreate.model_validate(
            {"name": "No lenses", "objective": "Must be rejected.", **payload}
        )


def test_repository_builds_alert_child_with_defaulted_values() -> None:
    session = RecordingSession()
    definition = ObservationCreate.model_validate(
        {
            "name": "Release health",
            "objective": "Observe release alerts.",
            "alert_lenses": [
                {
                    "id": "release-alerts",
                    "type": "alert",
                    "name": "Release alerts",
                    "source": "jira_track_and_release",
                    "selector": {"query": "project = REL"},
                }
            ],
        }
    )

    aggregate = asyncio.run(ObservationRepository().create(session, definition))

    assert aggregate.lenses == []
    assert aggregate.alert_lenses[0].selector_query == "project = REL"
    assert aggregate.alert_lenses[0].analysis_objectives == []
    assert aggregate.alert_lenses[0].reference_periods == []


class StubAdapter:
    async def query_range(self, *args, **kwargs) -> PrometheusRangeQueryResult:
        start = kwargs["start"]
        end = kwargs["end"]
        return PrometheusRangeQueryResult(
            resolved_start=start,
            resolved_end=end,
            step_seconds=60,
            series=[
                PrometheusRangeSeries(
                    labels={"job": "cooling"},
                    samples=[
                        PrometheusRangeSample(start, "12.5"),
                        PrometheusRangeSample(end, "NaN"),
                        PrometheusRangeSample(end, "+Inf"),
                    ],
                )
            ],
            warnings=["partial response"],
        )


def test_preflight_translates_typed_samples_and_warnings(monkeypatch) -> None:
    import app.observations.service as service_module

    monkeypatch.setattr(service_module, "get_settings", configured_settings)
    response = asyncio.run(
        ObservationDefinitionService().preflight_metric(
            MetricPreflightRequest.model_validate(
                {
                    "source_id": "production-prometheus",
                    "query": "avg(coolant_temperature_celsius)",
                    "validation_window": {"duration": "60m"},
                }
            ),
            StubAdapter(),
            now=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
        )
    )

    assert response.valid is True
    assert [sample.value_status for sample in response.samples] == [
        "finite",
        "nan",
        "positive_infinity",
    ]
    assert response.warnings == ["partial response"]


class MultipleSeriesAdapter:
    async def query_range(self, *args, **kwargs) -> PrometheusRangeQueryResult:
        start = kwargs["start"]
        return PrometheusRangeQueryResult(
            resolved_start=start,
            resolved_end=start + timedelta(minutes=60),
            step_seconds=60,
            series=[
                PrometheusRangeSeries(labels={"instance": str(index)}, samples=[])
                for index in range(12)
            ],
            warnings=[],
        )


def test_preflight_bounds_multiple_series_diagnostics(monkeypatch) -> None:
    import app.observations.service as service_module

    monkeypatch.setattr(service_module, "get_settings", configured_settings)
    response = asyncio.run(
        ObservationDefinitionService().preflight_metric(
            MetricPreflightRequest.model_validate(
                {
                    "source_id": "production-prometheus",
                    "query": "coolant_temperature_celsius",
                    "validation_window": {"duration": "60m"},
                }
            ),
            MultipleSeriesAdapter(),
            now=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
        )
    )

    assert response.valid is False
    assert response.code == "multiple_series_returned"
    assert response.series_count == 12
    assert len(response.label_sets) == 10
