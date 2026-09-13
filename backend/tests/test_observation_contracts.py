from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.core.settings import (
    BasicAuthCredentials,
    BearerTokenCredentials,
    PrometheusSourceSettings,
    Settings,
)
from app.infrastructure.persistence.repository import ObservationRepository
from app.infrastructure.prometheus.contracts import (
    PrometheusRangeQueryResult,
    PrometheusRangeSample,
    PrometheusRangeSeries,
)
from app.main import app
from app.observations.api import get_service
from app.observations.contracts import (
    CapabilitySource,
    MetricPreflightRequest,
    ObservationCreate,
    PrometheusSourceConfiguration,
)
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


def test_repository_serializes_optional_knowledge_scope_as_json_lists() -> None:
    """Strict API scope values persist through the JSONB-compatible aggregate field."""
    session = RecordingSession()
    definition = ObservationCreate.model_validate(
        {
            **valid_definition(),
            "knowledge_scope": {
                "service_ids": ["cooling-loop", "mprm-server"],
                "service_version": "2.x",
            },
        }
    )

    aggregate = asyncio.run(ObservationRepository().create(session, definition))

    assert aggregate.knowledge_scope == {
        "service_ids": ["cooling-loop", "mprm-server"],
        "service_version": "2.x",
    }


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


def test_capabilities_and_relative_hrefs_expose_only_safe_configuration(monkeypatch) -> None:
    import app.observations.service as service_module

    monkeypatch.setattr(service_module, "get_settings", configured_settings)
    service = ObservationDefinitionService()
    capabilities = service.capabilities()
    assert capabilities.model_dump() == {
        "metric": [
            {
                "adapter_type": "prometheus",
                "sources": [
                    {
                        "id": "production-prometheus",
                        "name": "Production Prometheus",
                        "configuration": {
                            "id": "production-prometheus",
                            "name": "Production Prometheus",
                            "base_url": "https://prometheus.example.test",
                            "credentials": {"type": "bearer_token"},
                        },
                    }
                ],
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
        knowledge_scope={"service_ids": ["cooling-loop"], "service_version": "2.x"},
    )
    summary = service.observation_summary(observation)
    assert summary.href == f"/api/v1/observations/{observation.id}"
    assert summary.knowledge_scope is not None
    assert summary.knowledge_scope.service_ids == ("cooling-loop",)


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            {
                "id": "primary",
                "name": "Primary metrics",
                "base_url": "https://prometheus.example.test",
                "credentials": {"type": "bearer_token"},
            },
            {"type": "bearer_token"},
        ),
        (
            {
                "id": "secondary",
                "name": "Secondary metrics",
                "base_url": "https://secondary.example.test",
                "credentials": {"type": "basic_auth", "username": "observe-reader"},
            },
            {"type": "basic_auth", "username": "observe-reader"},
        ),
    ],
)
def test_prometheus_source_configuration_validates_both_safe_credential_variants(
    payload: dict[str, object], expected: dict[str, str]
) -> None:
    configuration = PrometheusSourceConfiguration.model_validate(payload)

    assert configuration.credentials.model_dump() == expected


@pytest.mark.parametrize(
    "credentials",
    [
        {"type": "bearer_token", "token": "bearer-sentinel-secret"},
        {"type": "basic_auth", "username": "observe-reader", "password": "password-sentinel"},
    ],
)
def test_prometheus_source_configuration_rejects_secret_credential_fields(
    credentials: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        PrometheusSourceConfiguration.model_validate(
            {
                "id": "primary",
                "name": "Primary metrics",
                "base_url": "https://prometheus.example.test",
                "credentials": credentials,
            }
        )


def test_capability_source_requires_a_typed_configuration_projection() -> None:
    with pytest.raises(ValidationError):
        CapabilitySource.model_validate({"id": "primary", "name": "Primary metrics"})


def test_prometheus_source_configuration_omits_an_absent_base_url_when_serialized() -> None:
    configuration = PrometheusSourceConfiguration.model_validate(
        {
            "id": "primary",
            "name": "Primary metrics",
            "credentials": {"type": "bearer_token"},
        }
    )

    assert configuration.model_dump(exclude_none=True) == {
        "id": "primary",
        "name": "Primary metrics",
        "credentials": {"type": "bearer_token"},
    }


def test_capabilities_api_serializes_exact_safe_bearer_and_basic_configurations(
    monkeypatch,
) -> None:
    import app.observations.service as service_module

    bearer_secret = "bearer-sentinel-secret"
    basic_password = "basic-password-sentinel"
    settings = Settings(
        prometheus_sources=[
            PrometheusSourceSettings(
                id="primary",
                name="Primary metrics",
                base_url="https://primary.example.test/prometheus",
                credentials=BearerTokenCredentials(type="bearer_token", token=bearer_secret),
            ),
            PrometheusSourceSettings(
                id="secondary",
                name="Secondary metrics",
                base_url="https://secondary.example.test/prometheus",
                credentials=BasicAuthCredentials(
                    type="basic_auth", username="observe-reader", password=basic_password
                ),
            ),
        ]
    )
    monkeypatch.setattr(service_module, "get_settings", lambda: settings)
    service = ObservationDefinitionService()

    async def service_override() -> ObservationDefinitionService:
        return service

    async def request_capabilities() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/observation-definition-capabilities")

    app.dependency_overrides[get_service] = service_override
    try:
        response = asyncio.run(request_capabilities())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "metric": [
            {
                "adapter_type": "prometheus",
                "sources": [
                    {
                        "id": "primary",
                        "name": "Primary metrics",
                        "configuration": {
                            "id": "primary",
                            "name": "Primary metrics",
                            "base_url": "https://primary.example.test/prometheus",
                            "credentials": {"type": "bearer_token"},
                        },
                    },
                    {
                        "id": "secondary",
                        "name": "Secondary metrics",
                        "configuration": {
                            "id": "secondary",
                            "name": "Secondary metrics",
                            "base_url": "https://secondary.example.test/prometheus",
                            "credentials": {
                                "type": "basic_auth",
                                "username": "observe-reader",
                            },
                        },
                    },
                ],
            }
        ]
    }
    for protected in (
        '"token"',
        '"password"',
        bearer_secret,
        basic_password,
        "**********",
        "Authorization",
        "health",
        "diagnostic",
    ):
        assert protected not in response.text


@pytest.mark.parametrize(
    "base_url",
    [
        "https://reader:embedded-password-sentinel@prometheus.example.test",
        "https://prometheus.example.test/metrics?query-sentinel=1",
        "https://prometheus.example.test/metrics#fragment-sentinel",
        "https://",
        "ftp://prometheus.example.test",
        "https://prometheus.example.test/a//unsafe-path",
    ],
)
def test_capabilities_api_omits_every_rejected_prometheus_target_from_real_http_response(
    monkeypatch, base_url: str
) -> None:
    import app.observations.service as service_module

    bearer_secret = "bearer-sentinel-secret"
    settings = Settings(
        prometheus_sources=[
            PrometheusSourceSettings(
                id="unsafe",
                name="Unsafe metrics",
                base_url=base_url,
                credentials=BearerTokenCredentials(type="bearer_token", token=bearer_secret),
            )
        ]
    )
    monkeypatch.setattr(service_module, "get_settings", lambda: settings)
    service = ObservationDefinitionService()

    async def service_override() -> ObservationDefinitionService:
        return service

    async def request_capabilities() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/observation-definition-capabilities")

    app.dependency_overrides[get_service] = service_override
    try:
        response = asyncio.run(request_capabilities())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    configuration = response.json()["metric"][0]["sources"][0]["configuration"]
    assert configuration == {
        "id": "unsafe",
        "name": "Unsafe metrics",
        "credentials": {"type": "bearer_token"},
    }
    for protected in (
        base_url,
        "embedded-password-sentinel",
        "query-sentinel",
        "fragment-sentinel",
        bearer_secret,
        '"token"',
        '"password"',
        "**********",
        "Authorization",
        "health",
        "diagnostic",
    ):
        assert protected not in response.text


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


def valid_alert_lens() -> dict:
    return {
        "id": "release-alerts",
        "type": "alert",
        "name": "Release alerts",
        "description": "Release signal",
        "source": "jira_track_and_release",
        "selector": {"query": " project = REL AND status != Done "},
        "analysis_objectives": ["Assess recurrence", "Assess impact"],
        "reference_periods": ["1d", "7d"],
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda alert: alert.update(id="not valid"),
        lambda alert: alert.update(type="metric"),
        lambda alert: alert.update(name=" \t"),
        lambda alert: alert.update(description="\n"),
        lambda alert: alert.update(source="jira"),
        lambda alert: alert.update(selector={}),
        lambda alert: alert.update(selector={"query": "  "}),
        lambda alert: alert.update(analysis_objectives=["useful", "useful"]),
        lambda alert: alert.update(analysis_objectives=["useful", " \t"]),
        lambda alert: alert.update(reference_periods=["0m"]),
        lambda alert: alert.update(reference_periods=["1d", "1d"]),
    ],
)
def test_alert_contract_rejects_each_invalid_recognized_member(mutate) -> None:
    alert = valid_alert_lens()
    mutate(alert)

    with pytest.raises(ValidationError):
        ObservationCreate.model_validate(
            {"name": "Release health", "objective": "Observe alerts.", "alert_lenses": [alert]}
        )


def test_alert_contract_preserves_exact_opaque_strings_and_order() -> None:
    alert = valid_alert_lens()
    definition = ObservationCreate.model_validate(
        {"name": "Release health", "objective": "Observe alerts.", "alert_lenses": [alert]}
    )

    accepted = definition.alert_lenses[0]
    assert accepted.selector.query == " project = REL AND status != Done "
    assert accepted.analysis_objectives == ["Assess recurrence", "Assess impact"]
    assert accepted.reference_periods == ["1d", "7d"]


def test_type_local_ids_and_metric_only_relationship_resolution() -> None:
    definition = valid_definition()
    metric = definition["lenses"][0]
    metric["id"] = "shared"
    definition["lenses"] = [metric, definition["lenses"][1]]
    definition["alert_lenses"] = [dict(valid_alert_lens(), id="shared")]
    definition["relationships"][0]["participants"] = ["shared", "coolant-pressure"]
    definition["relationships"][0]["expected"] = {
        "shared": {"trend": {"direction": "increasing"}},
        "coolant-pressure": {"variability": {"state": "low"}},
    }

    accepted = ObservationCreate.model_validate(definition)
    assert [lens.id for lens in accepted.lenses] == ["shared", "coolant-pressure"]
    assert [lens.id for lens in accepted.alert_lenses] == ["shared"]

    alert_only_participant = deepcopy(definition)
    alert_only_participant["relationships"][0]["participants"] = ["shared", "release-alerts"]
    alert_only_participant["relationships"][0]["expected"] = {
        "shared": {"trend": {"direction": "increasing"}},
        "release-alerts": {"variability": {"state": "low"}},
    }
    alert_only_participant["alert_lenses"].append(dict(valid_alert_lens(), id="release-alerts"))
    with pytest.raises(ValidationError):
        ObservationCreate.model_validate(alert_only_participant)


@pytest.mark.parametrize(
    "collection",
    [
        "lenses",
        "alert_lenses",
    ],
)
def test_duplicate_ids_are_rejected_only_within_their_type(collection) -> None:
    definition = valid_definition()
    if collection == "lenses":
        definition["lenses"].append(deepcopy(definition["lenses"][0]))
    else:
        definition["alert_lenses"] = [valid_alert_lens(), valid_alert_lens()]

    with pytest.raises(ValidationError):
        ObservationCreate.model_validate(definition)


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
