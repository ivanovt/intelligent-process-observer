"""VS-02 HTTP-boundary tests for the production Prometheus Metric provider."""

from __future__ import annotations

import asyncio
import json
import math
import ssl
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest

from app.core.settings import BasicAuthCredentials, BearerTokenCredentials, PrometheusSourceSettings
from app.infrastructure.prometheus.composition import (
    PrometheusMetricSeriesProvider,
    _AttemptFailure,
    _AttemptRetryEligible,
    _AttemptTimeout,
    _classify_complete_response,
)
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricProviderScope,
    MetricSeriesAcquisitionFailure,
    MetricSeriesAvailable,
)

_START = datetime(2026, 9, 1, 12, tzinfo=UTC)


def _source(
    *,
    base_url: str = "https://prometheus.example.test/prometheus",
    credentials: BearerTokenCredentials | BasicAuthCredentials | None = None,
) -> PrometheusSourceSettings:
    return PrometheusSourceSettings(
        id="plant-prometheus",
        name="Plant Prometheus",
        base_url=base_url,
        credentials=credentials
        or BearerTokenCredentials(type="bearer_token", token="bearer-sentinel-secret"),
    )


def _scope(query: str = "up{job='plant'}") -> MetricProviderScope:
    return MetricProviderScope(adapter_type="prometheus", source_id="plant-prometheus", query=query)


def _window(seconds: float = 60) -> MetricAnalysisWindow:
    return MetricAnalysisWindow(**{"from": _START, "to": _START + timedelta(seconds=seconds)})


def _provider(source: PrometheusSourceSettings, handler):
    return PrometheusMetricSeriesProvider(
        [source], client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


def _success(result, **annotations):
    return {"status": "success", "data": {"resultType": "matrix", "result": result}, **annotations}


def _acquire(provider: PrometheusMetricSeriesProvider, window: MetricAnalysisWindow | None = None):
    window = window or _window()
    return asyncio.run(provider.acquire(_scope(), window))


def test_default_client_disables_redirects_and_environment_proxies_with_tls_verification() -> None:
    client = PrometheusMetricSeriesProvider._new_client()
    try:
        assert client.follow_redirects is False
        assert client._trust_env is False  # noqa: SLF001 - HTTPX has no public inspection API.
        assert client._transport._pool._ssl_context.verify_mode == ssl.CERT_REQUIRED  # noqa: SLF001
    finally:
        asyncio.run(client.aclose())


@pytest.mark.parametrize(
    ("base_url", "seconds", "expected_path", "expected_step"),
    [
        ("https://prometheus.example.test", 0.5, "/api/v1/query_range", "1"),
        ("https://prometheus.example.test/", 60, "/api/v1/query_range", "1"),
        (
            "https://prometheus.example.test/prometheus",
            60.001,
            "/prometheus/api/v1/query_range",
            "2",
        ),
        (
            "https://prometheus.example.test/monitoring/prometheus/",
            3600,
            "/monitoring/prometheus/api/v1/query_range",
            "60",
        ),
        (
            "https://prometheus.example.test/prometheus",
            3600.001,
            "/prometheus/api/v1/query_range",
            "61",
        ),
    ],
)
def test_one_attempt_posts_exact_immutable_range_request(
    base_url: str, seconds: float, expected_path: str, expected_step: str
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_success([]))

    outcome = _acquire(_provider(_source(base_url=base_url), handler), _window(seconds))

    assert outcome == MetricSeriesAvailable(source="prometheus", samples=())
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == expected_path
    assert request.url.query == b""
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert parse_qs(request.content.decode(), strict_parsing=True) == {
        "query": ["up{job='plant'}"],
        "start": [_START.isoformat().replace("+00:00", "Z")],
        "end": [(_START + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")],
        "step": [expected_step],
        "timeout": ["10s"],
        "limit": ["2"],
    }


@pytest.mark.parametrize(
    "credentials, expected_authorization",
    [
        (
            BearerTokenCredentials(type="bearer_token", token="bearer-sentinel-secret"),
            "Bearer bearer-sentinel-secret",
        ),
        (
            BasicAuthCredentials(
                type="basic_auth", username="reader-sentinel", password="password-sentinel"
            ),
            "Basic cmVhZGVyLXNlbnRpbmVsOnBhc3N3b3JkLXNlbnRpbmVs",
        ),
    ],
)
def test_authentication_is_preemptive_and_never_enters_outcomes(
    credentials: BearerTokenCredentials | BasicAuthCredentials, expected_authorization: str
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://other.example.test/steal"})

    provider = _provider(_source(credentials=credentials), handler)
    outcome = _acquire(provider)

    assert outcome == MetricSeriesAcquisitionFailure(diagnostic="prometheus_acquisition_failed")
    assert len(requests) == 1
    assert requests[0].headers["authorization"] == expected_authorization
    rendered = repr(outcome)
    for protected in (
        "bearer-sentinel-secret",
        "reader-sentinel",
        "password-sentinel",
        "other.example.test",
    ):
        assert protected not in rendered


def test_valid_float_matrix_preserves_order_and_non_finite_values() -> None:
    payload = _success(
        [
            {
                "metric": {"instance": "private-label"},
                "values": [[10, "2.0"], [20.5, "NaN"], [30, "+Inf"], [40, "-Inf"]],
            }
        ]
    )
    outcome = _acquire(_provider(_source(), lambda _: httpx.Response(200, json=payload)))

    assert isinstance(outcome, MetricSeriesAvailable)
    assert [sample.timestamp for sample in outcome.samples] == [
        datetime.fromtimestamp(10, UTC),
        datetime.fromtimestamp(20.5, UTC),
        datetime.fromtimestamp(30, UTC),
        datetime.fromtimestamp(40, UTC),
    ]
    assert outcome.samples[0].value == 2.0
    assert math.isnan(outcome.samples[1].value)
    assert outcome.samples[2].value == float("inf")
    assert outcome.samples[3].value == float("-inf")


def test_exactly_sixty_one_float_samples_are_accepted() -> None:
    payload = _success([{"metric": {}, "values": [[index, "1"] for index in range(61)]}])

    outcome = _acquire(_provider(_source(), lambda _: httpx.Response(200, json=payload)))

    assert isinstance(outcome, MetricSeriesAvailable)
    assert len(outcome.samples) == 61


@pytest.mark.parametrize(
    "payload",
    [
        _success([{"metric": {}, "values": []}, {"metric": {}, "values": []}]),
        _success([{"metric": {}, "values": [], "histograms": []}]),
        _success([{"metric": {"bad": 1}, "values": []}]),
        _success([{"metric": {}, "values": [[True, "1"]]}]),
        _success([{"metric": {}, "values": [[1, 1]]}]),
        _success([{"metric": {}, "values": [[1, "not-a-number"]]}]),
        _success([{"metric": {}, "values": [[index, "1"] for index in range(62)]}]),
        _success([], warnings=["provider-warning-sentinel"]),
        _success([], infos="not-an-array"),
        {"status": "success", "data": {"resultType": "vector", "result": []}},
    ],
)
def test_unrepresentable_success_shapes_fail_closed(payload: dict) -> None:
    outcome = _acquire(_provider(_source(), lambda _: httpx.Response(200, json=payload)))

    assert outcome == MetricSeriesAcquisitionFailure(diagnostic="prometheus_acquisition_failed")
    assert "provider-warning-sentinel" not in repr(outcome)


@pytest.mark.parametrize("status_code", [429, 500, 502, 504])
def test_complete_malformed_retryable_status_is_private_retry_eligible(status_code: int) -> None:
    result = _classify_complete_response(status_code, b"not-json")

    assert result == _AttemptRetryEligible(status_code=status_code)


def test_timeout_and_canceled_error_envelopes_win_before_status_retry_policy() -> None:
    payload = json.dumps(
        {"status": "error", "errorType": "timeout", "error": "provider-secret", "warnings": []}
    ).encode()

    assert isinstance(_classify_complete_response(503, payload), _AttemptTimeout)
    assert isinstance(_classify_complete_response(503, b'{"status":"error"}'), _AttemptFailure)


def test_oversized_declared_response_fails_before_retryable_status_and_closes() -> None:
    closed = False

    class ClosingStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"{}"

        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"content-length": str(1024 * 1024 + 1)},
            stream=ClosingStream(),
        )

    outcome = _acquire(_provider(_source(), handler))

    assert outcome == MetricSeriesAcquisitionFailure(diagnostic="prometheus_acquisition_failed")
    assert closed is True


def test_exact_one_mebibyte_complete_success_body_is_accepted() -> None:
    body = json.dumps(_success([])).encode()
    body += b" " * (1024 * 1024 - len(body))

    outcome = _acquire(_provider(_source(), lambda _: httpx.Response(200, content=body)))

    assert outcome == MetricSeriesAvailable(source="prometheus", samples=())


def test_streamed_response_over_the_cap_fails_and_closes_without_classifying_status() -> None:
    closed = False

    class ClosingStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"{" + b" " * (1024 * 1024)
            yield b"}"

        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(504, stream=ClosingStream())

    outcome = _acquire(_provider(_source(), handler))

    assert outcome == MetricSeriesAcquisitionFailure(diagnostic="prometheus_acquisition_failed")
    assert closed is True
