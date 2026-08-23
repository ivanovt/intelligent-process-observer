from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core.settings import BasicAuthCredentials, BearerTokenCredentials
from app.infrastructure.prometheus.adapter import (
    HttpxPrometheusQueryAdapter,
    PrometheusAuthenticationError,
    PrometheusQueryError,
    PrometheusTransportError,
)
from app.infrastructure.prometheus.contracts import PrometheusSourceProfile


class StubResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class StubClient:
    def __init__(self, response: StubResponse | Exception) -> None:
        self.response = response
        self.request: dict | None = None

    async def __aenter__(self) -> StubClient:
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def post(self, url: str, **kwargs) -> StubResponse:
        self.request = {"url": url, **kwargs}
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def source(credentials=None) -> PrometheusSourceProfile:
    return PrometheusSourceProfile(
        id="production-prometheus",
        name="Production Prometheus",
        base_url="https://prometheus.example.test/",
        credentials=credentials
        or BearerTokenCredentials(type="bearer_token", token="secret-token"),
    )


def test_range_query_posts_with_bearer_auth_and_returns_provider_warnings(monkeypatch) -> None:
    response = StubResponse(
        200,
        {
            "status": "success",
            "warnings": ["partial response"],
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"job": "cooling"},
                        "values": [[1787400000, "12.5"]],
                    }
                ],
            },
        },
    )
    client = StubClient(response)
    client_configuration: dict = {}

    def create_client(**kwargs):
        client_configuration.update(kwargs)
        return client

    monkeypatch.setattr("app.infrastructure.prometheus.adapter.httpx.AsyncClient", create_client)
    start = datetime(2026, 8, 22, 10, 0, tzinfo=UTC)
    end = start + timedelta(minutes=60)

    result = asyncio.run(
        HttpxPrometheusQueryAdapter().query_range(
            source(), query="avg(coolant_temperature_celsius)", start=start, end=end
        )
    )

    assert client.request is not None
    assert client.request["url"] == "https://prometheus.example.test/api/v1/query_range"
    assert client.request["headers"] == {"Authorization": "Bearer secret-token"}
    assert client.request["data"]["step"] == 60
    assert client_configuration["timeout"] == 15.0
    assert result.series[0].labels == {"job": "cooling"}
    assert result.warnings == ["partial response"]


def test_range_query_uses_basic_auth_when_configured(monkeypatch) -> None:
    client = StubClient(
        StubResponse(200, {"status": "success", "data": {"resultType": "matrix", "result": []}})
    )
    monkeypatch.setattr(
        "app.infrastructure.prometheus.adapter.httpx.AsyncClient", lambda **_kwargs: client
    )
    start = datetime(2026, 8, 22, 10, 0, tzinfo=UTC)

    asyncio.run(
        HttpxPrometheusQueryAdapter().query_range(
            source(BasicAuthCredentials(type="basic_auth", username="reader", password="secret")),
            query="up",
            start=start,
            end=start + timedelta(minutes=1),
        )
    )

    assert client.request is not None
    assert isinstance(client.request["auth"], httpx.BasicAuth)
    assert client.request["headers"] == {}


@pytest.mark.parametrize(
    ("response", "exception"),
    [
        (StubResponse(400, {"error": "bad PromQL"}), PrometheusQueryError),
        (StubResponse(401, {}), PrometheusAuthenticationError),
        (StubResponse(503, {}), PrometheusTransportError),
        (httpx.TimeoutException("too slow"), PrometheusTransportError),
    ],
)
def test_range_query_maps_provider_and_transport_failures(
    monkeypatch, response: StubResponse | Exception, exception: type[Exception]
) -> None:
    client = StubClient(response)
    monkeypatch.setattr(
        "app.infrastructure.prometheus.adapter.httpx.AsyncClient", lambda **_kwargs: client
    )
    start = datetime(2026, 8, 22, 10, 0, tzinfo=UTC)

    with pytest.raises(exception):
        asyncio.run(
            HttpxPrometheusQueryAdapter().query_range(
                source(), query="up", start=start, end=start + timedelta(minutes=1)
            )
        )
