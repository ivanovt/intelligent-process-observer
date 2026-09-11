"""VS-01 configuration-boundary tests for the production Metric provider."""

from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core.settings import (
    BasicAuthCredentials,
    BearerTokenCredentials,
    PrometheusSourceSettings,
    Settings,
)
from app.infrastructure.prometheus.adapter import HttpxPrometheusQueryAdapter
from app.infrastructure.prometheus.composition import PrometheusMetricSeriesProvider
from app.infrastructure.prometheus.contracts import (
    PrometheusRangeQueryResult,
    PrometheusRangeSeries,
)
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricProviderScope,
    MetricSeriesAcquisitionFailure,
    MetricSeriesUnavailable,
)
from app.metrics.ports import MetricSeriesProvider
from app.observations.contracts import MetricPreflightRequest, ObservationCreate
from app.observations.service import ObservationDefinitionService

_START = datetime(2026, 9, 1, tzinfo=UTC)


def _source(
    base_url: str,
    *,
    source_id: str = "plant-prometheus",
    credentials: BearerTokenCredentials | BasicAuthCredentials | None = None,
) -> PrometheusSourceSettings:
    return PrometheusSourceSettings(
        id=source_id,
        name="Plant Prometheus",
        base_url=base_url,
        credentials=credentials
        or BearerTokenCredentials(type="bearer_token", token="bearer-sentinel-secret"),
    )


def _scope(source_id: str = "plant-prometheus") -> MetricProviderScope:
    return MetricProviderScope(adapter_type="prometheus", source_id=source_id, query="up")


def _window() -> MetricAnalysisWindow:
    return MetricAnalysisWindow(**{"from": _START, "to": _START + timedelta(minutes=1)})


def _acquire(provider: PrometheusMetricSeriesProvider, source_id: str = "plant-prometheus"):
    return asyncio.run(provider.acquire(_scope(source_id), _window()))


def _assert_safe_failure(outcome: object, diagnostic: str):
    assert isinstance(outcome, MetricSeriesAcquisitionFailure)
    assert outcome.diagnostic == diagnostic
    return outcome


def _provider(sources: list[PrometheusSourceSettings]) -> PrometheusMetricSeriesProvider:
    def response(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "success", "data": {"resultType": "matrix", "result": []}}
        )

    return PrometheusMetricSeriesProvider(
        sources,
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(response)),
    )


def _accepts_port(provider: MetricSeriesProvider) -> MetricSeriesProvider:
    return provider


def test_absent_or_unknown_source_is_exact_and_never_falls_back() -> None:
    absent = _provider([])
    configured = _provider(
        [
            _source("https://first.example.test", source_id="first"),
            _source("https://second.example.test", source_id="second"),
        ]
    )

    assert _acquire(absent) == MetricSeriesUnavailable(diagnostic="prometheus_source_unavailable")
    assert _acquire(configured, "missing") == MetricSeriesUnavailable(
        diagnostic="prometheus_source_unavailable"
    )
    assert _acquire(configured, "second").source == "prometheus"


@pytest.mark.parametrize(
    "base_url",
    [
        "https://prometheus.example.test",
        "https://prometheus.example.test/",
        "https://prometheus.example.test/prometheus",
        "https://prometheus.example.test/team.v1/_prom~etheus-2/metrics/",
        "https://127.0.0.1:9443/prometheus",
        "http://localhost",
        "http://127.0.0.1:9090/metrics",
        "http://[::1]:9090/metrics",
    ],
)
def test_valid_production_targets_reach_the_injected_transport(base_url: str) -> None:
    outcome = _acquire(_provider([_source(base_url)]))

    assert outcome.samples == ()


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://prometheus.example.test",
        "http://prometheus.example.test",
        "https://",
        "https://user:password@prometheus.example.test",
        "https://prometheus.example.test?query=1",
        "https://prometheus.example.test#fragment",
        "https://prometheus.example.test/a//b",
        "https://prometheus.example.test/a//",
        "https://prometheus.example.test/./a",
        "https://prometheus.example.test/a/../b",
        "https://prometheus.example.test/a\\b",
        "https://prometheus.example.test/%41",
        "https://prometheus.example.test/%2F",
        "https://prometheus.example.test/%2e%2e",
        "https://prometheus.example.test/%2E%2E",
        "https://prometheus.example.test/a b",
        "https://prometheus.example.test/a\tb",
        "http://127.0.0.2",
        "http://[::2]",
        "https://prometheus.example.test:0",
        "https://prometheus.example.test:65536",
    ],
)
def test_invalid_selected_target_is_rejected_before_any_transport(base_url: str) -> None:
    outcome = _acquire(_provider([_source(base_url)]))

    failure = _assert_safe_failure(outcome, "prometheus_source_invalid")
    assert failure.diagnostic_category == "source_invalid"


def test_production_validation_does_not_change_shared_settings_or_leak_credentials() -> None:
    bearer = "bearer-sentinel-secret"
    username = "reader-sentinel"
    password = "basic-password-sentinel"
    selected = _source(
        "https://reader:password@prometheus.example.test/a//b",
        credentials=BasicAuthCredentials(type="basic_auth", username=username, password=password),
    )
    unselected = _source(
        "https://safe.example.test",
        source_id="other",
        credentials=BearerTokenCredentials(type="bearer_token", token=bearer),
    )
    settings = Settings(prometheus_sources=[selected, unselected])
    provider = _provider(settings.prometheus_sources)

    outcome = _acquire(provider)
    rendered = f"{outcome!r} {provider!r}"

    assert settings.prometheus_sources == [selected, unselected]
    failure = _assert_safe_failure(outcome, "prometheus_source_invalid")
    assert failure.diagnostic_category == "source_invalid"
    for protected in (bearer, username, password, "Authorization"):
        assert protected not in rendered


def test_provider_is_port_only() -> None:
    provider = _provider([_source("https://prometheus.example.test")])

    assert _accepts_port(provider) is provider
    assert "app.metrics" not in inspect.getsource(PrometheusMetricSeriesProvider)


class _PreflightAdapter:
    async def query_range(self, *args, **kwargs) -> PrometheusRangeQueryResult:
        return PrometheusRangeQueryResult(
            resolved_start=kwargs["start"],
            resolved_end=kwargs["end"],
            step_seconds=60,
            series=[PrometheusRangeSeries(labels={}, samples=[])],
            warnings=[],
        )


class _ReachedRepository:
    async def create(self, session, definition):
        del session, definition
        raise RuntimeError("repository reached")


class _Transaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *args):
        return None


class _Session:
    def begin(self) -> _Transaction:
        return _Transaction()


@pytest.mark.parametrize(
    "base_url",
    [
        "https://prometheus.example.test/prometheus",
        "https://reader:password@prometheus.example.test",
    ],
)
def test_shared_consumers_remain_compatible_for_valid_and_production_invalid_sources(
    monkeypatch, base_url: str
) -> None:
    import app.main as main_module
    import app.observations.service as service_module

    settings = Settings(prometheus_sources=[_source(base_url)])
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(service_module, "get_settings", lambda: settings)

    class _NoActiveRuntimeState:
        """Keep this provider-composition test independent from persistence availability."""

        def __init__(self, *_args) -> None:
            pass

        async def reconcile_active_observation_runs(self) -> None:
            return None

        async def has_active_observation_runs(self) -> bool:
            return False

        async def get_active_observation_run_id(self, _observation_id):
            return None

    monkeypatch.setattr(main_module, "RuntimeExecutionStateStore", _NoActiveRuntimeState)

    async def exercise() -> None:
        async with main_module.lifespan(main_module.app):
            provider = main_module.app.state.metric_series_provider
            service = main_module.app.state.observation_service
            assert isinstance(provider, PrometheusMetricSeriesProvider)
            assert isinstance(main_module.app.state.prometheus_adapter, HttpxPrometheusQueryAdapter)
            assert service.capabilities().metric[0].sources[0].id == "plant-prometheus"
            assert "health" not in service.capabilities().model_dump_json()
            assert "diagnostic" not in service.capabilities().model_dump_json()
            preflight = await service.preflight_metric(
                MetricPreflightRequest(
                    source_id="plant-prometheus", query="up", validation_window={"duration": "1m"}
                ),
                _PreflightAdapter(),
                now=_START,
            )
            assert preflight.valid is True
            create_service = ObservationDefinitionService(_ReachedRepository())
            definition = ObservationCreate.model_validate(
                {
                    "name": "Metric source compatibility",
                    "objective": "Keep shared consumers compatible.",
                    "lenses": [
                        {
                            "id": "metric-source",
                            "name": "Metric source",
                            "type": "metric",
                            "metric_id": "up",
                            "adapter_type": "prometheus",
                            "source_id": "plant-prometheus",
                            "query": "up",
                            "unit": "count",
                            "analysis_objectives": [],
                            "reference_periods": [],
                        }
                    ],
                }
            )
            with pytest.raises(RuntimeError, match="repository reached"):
                await create_service.create(_Session(), definition)
            if "@" in base_url:
                outcome = await provider.acquire(_scope(), _window())
                assert outcome.diagnostic == "prometheus_source_invalid"

    asyncio.run(exercise())
