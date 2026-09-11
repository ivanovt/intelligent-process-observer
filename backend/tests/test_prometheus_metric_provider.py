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
    _LogicalRangeQuery,
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


def _assert_safe_failure(outcome: object, diagnostic: str = "prometheus_acquisition_failed"):
    assert isinstance(outcome, MetricSeriesAcquisitionFailure)
    assert outcome.diagnostic == diagnostic
    return outcome


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
        ("https://prometheus.example.test/", 1.25, "/api/v1/query_range", "1"),
        (
            "https://prometheus.example.test/prometheus",
            59.999,
            "/prometheus/api/v1/query_range",
            "1",
        ),
        ("https://prometheus.example.test/", 60, "/api/v1/query_range", "1"),
        (
            "https://prometheus.example.test/prometheus",
            60.001,
            "/prometheus/api/v1/query_range",
            "2",
        ),
        (
            "https://prometheus.example.test/prometheus",
            119.999,
            "/prometheus/api/v1/query_range",
            "2",
        ),
        (
            "https://prometheus.example.test/prometheus",
            120,
            "/prometheus/api/v1/query_range",
            "2",
        ),
        (
            "https://prometheus.example.test/prometheus",
            120.001,
            "/prometheus/api/v1/query_range",
            "3",
        ),
        (
            "https://prometheus.example.test/monitoring/prometheus/",
            3599.999,
            "/monitoring/prometheus/api/v1/query_range",
            "60",
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
    form = parse_qs(request.content.decode(), strict_parsing=True)
    assert form == {
        "query": ["up{job='plant'}"],
        "start": [_START.isoformat().replace("+00:00", "Z")],
        "end": [(_START + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")],
        "step": [expected_step],
        "timeout": ["10s"],
        "limit": ["2"],
    }
    assert math.floor(seconds / int(form["step"][0])) + 1 <= 61


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

    _assert_safe_failure(outcome)
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

    _assert_safe_failure(outcome)
    assert "provider-warning-sentinel" not in repr(outcome)


def test_valid_success_infos_are_discarded_without_changing_available_data() -> None:
    info_text = "provider-info-must-not-leak"
    outcome = _acquire(
        _provider(
            _source(),
            lambda _: httpx.Response(200, json=_success([], warnings=[], infos=[info_text])),
        )
    )

    assert outcome == MetricSeriesAvailable(source="prometheus", samples=())
    assert info_text not in repr(outcome)


@pytest.mark.parametrize(
    "annotations",
    [
        {"warnings": "not-an-array"},
        {"warnings": ["valid", 1]},
        {"infos": "not-an-array"},
        {"infos": ["valid", 1]},
        {"warnings": [], "infos": ["valid", 1]},
    ],
)
def test_malformed_success_annotations_fail_closed_without_provider_text_leakage(
    annotations: dict,
) -> None:
    outcome = _acquire(
        _provider(_source(), lambda _: httpx.Response(200, json=_success([], **annotations)))
    )

    _assert_safe_failure(outcome)
    assert "not-an-array" not in repr(outcome)
    assert "['valid', 1]" not in repr(outcome)


@pytest.mark.parametrize("status_code", [429, 500, 502, 504])
def test_retryable_status_body_precedence_pairs_bounded_malformed_and_oversized_body(
    status_code: int,
) -> None:
    bounded = _classify_complete_response(status_code, b"not-json")

    assert bounded == _AttemptRetryEligible(status_code=status_code)

    closed = False

    class ClosingStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"{}"

        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            headers={"content-length": str(1024 * 1024 + 1)},
            stream=ClosingStream(),
        )

    oversized = asyncio.run(
        _provider(_source(), handler)._execute_one_attempt(
            _LogicalRangeQuery(
                url="https://prometheus.example.test/api/v1/query_range",
                form=(),
                headers=(),
                auth=None,
            )
        )
    )

    assert oversized == _AttemptFailure(category="response_too_large", http_status=status_code)
    assert closed is True


@pytest.mark.parametrize("error_type", ["timeout", "canceled"])
@pytest.mark.parametrize("status_code", [429, 500, 502, 504])
@pytest.mark.parametrize(
    "annotations",
    [
        {"warnings": ["provider-warning-must-not-leak"]},
        {"infos": ["provider-info-must-not-leak"]},
    ],
)
def test_valid_timeout_and_canceled_error_envelopes_override_retryable_statuses(
    error_type: str, status_code: int, annotations: dict[str, list[str]]
) -> None:
    provider_text = "provider-text-must-not-leak"
    payload = json.dumps(
        {
            "status": "error",
            "errorType": error_type,
            "error": provider_text,
            **annotations,
        }
    ).encode()

    result = _classify_complete_response(status_code, payload)

    assert result == _AttemptTimeout(category="transport_timeout")
    rendered = repr(result)
    assert provider_text not in rendered
    assert "provider-warning-must-not-leak" not in rendered
    assert "provider-info-must-not-leak" not in rendered


@pytest.mark.parametrize(
    "payload",
    [
        {"errorType": "timeout", "error": "provider-text-must-not-leak"},
        {"status": 1, "errorType": "timeout", "error": "provider-text-must-not-leak"},
        {
            "status": "success",
            "errorType": "timeout",
            "error": "provider-text-must-not-leak",
        },
        {
            "status": "not-error",
            "errorType": "timeout",
            "error": "provider-text-must-not-leak",
        },
        {"status": "error", "error": "provider-text-must-not-leak"},
        {"status": "error", "errorType": "", "error": "provider-text-must-not-leak"},
        {"status": "error", "errorType": 1, "error": "provider-text-must-not-leak"},
        {"status": "error", "errorType": "timeout"},
        {"status": "error", "errorType": "timeout", "error": ""},
        {"status": "error", "errorType": "timeout", "error": 1},
        {
            "status": "error",
            "errorType": "timeout",
            "error": "provider-text-must-not-leak",
            "warnings": "not-an-array",
        },
    ],
)
def test_invalid_error_envelopes_do_not_prove_timeout_on_503(payload: dict) -> None:
    result = _classify_complete_response(503, json.dumps(payload).encode())

    assert result == _AttemptFailure(category="http_status_failure", http_status=503)
    assert "provider-text-must-not-leak" not in repr(result)


@pytest.mark.parametrize("malformed_infos", ["not-an-array", ["valid", 1]])
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (503, _AttemptFailure(category="http_status_failure", http_status=503)),
        (429, _AttemptRetryEligible(status_code=429)),
        (500, _AttemptRetryEligible(status_code=500)),
        (502, _AttemptRetryEligible(status_code=502)),
        (504, _AttemptRetryEligible(status_code=504)),
    ],
)
def test_malformed_infos_on_error_envelopes_follow_status_policy(
    malformed_infos: str | list[str | int], status_code: int, expected: object
) -> None:
    provider_text = "provider-text-must-not-leak"
    result = _classify_complete_response(
        status_code,
        json.dumps(
            {
                "status": "error",
                "errorType": "timeout",
                "error": provider_text,
                "infos": malformed_infos,
            }
        ).encode(),
    )

    assert result == expected
    assert provider_text not in repr(result)


@pytest.mark.parametrize(
    ("status_code", "body"),
    [
        (503, b""),
        (503, b"not-json"),
        (503, b'{"status":"error"}'),
        (400, b'{"status":"error","errorType":"bad_data","error":"provider-text-must-not-leak"}'),
        (422, b'{"status":"error","errorType":"bad_data","error":"provider-text-must-not-leak"}'),
        (501, b'{"status":"error","errorType":"bad_data","error":"provider-text-must-not-leak"}'),
    ],
)
def test_bare_malformed_503_and_other_non_retryable_statuses_are_terminal_failures(
    status_code: int, body: bytes
) -> None:
    result = _classify_complete_response(status_code, body)

    category = "query_rejected" if b'"errorType":"bad_data"' in body else "http_status_failure"
    assert result == _AttemptFailure(category=category, http_status=status_code)
    assert "provider-text-must-not-leak" not in repr(result)


@pytest.mark.parametrize(
    ("status_code", "payload", "category"),
    [
        (
            401,
            {"status": "error", "errorType": "bad_data", "error": "provider-text"},
            "authentication_failed",
        ),
        (
            400,
            {"status": "error", "errorType": "bad_data", "error": "provider-text"},
            "query_rejected",
        ),
        (
            418,
            {"status": "unexpected", "error": "provider-text"},
            "http_status_failure",
        ),
        (
            200,
            {"status": "success", "data": {"resultType": "vector", "result": []}},
            "response_invalid",
        ),
        (200, _success([], warnings=["provider-warning"]), "provider_warning"),
        (
            200,
            _success(
                [
                    {"metric": {"unsafe": "provider-label"}, "values": []},
                    {"metric": {"unsafe": "another-label"}, "values": []},
                ]
            ),
            "multiple_series_returned",
        ),
        (
            200,
            _success(
                [
                    {
                        "metric": {"unsafe": "provider-label"},
                        "values": [[_START.timestamp(), "not-a-float"]],
                    }
                ]
            ),
            "invalid_sample_data",
        ),
    ],
)
def test_complete_response_failure_categories_are_closed_and_discard_provider_content(
    status_code: int, payload: dict, category: str
) -> None:
    """Classification retains only the safe category and bounded approved metadata."""
    result = _classify_complete_response(status_code, json.dumps(payload).encode())

    assert isinstance(result, _AttemptFailure)
    assert result.category == category
    assert "provider-text" not in repr(result)
    assert "provider-warning" not in repr(result)
    assert "provider-label" not in repr(result)
    assert "another-label" not in repr(result)


@pytest.mark.parametrize("status_code", [429, 500, 502, 504])
def test_retryable_status_precedes_valid_non_timeout_error_type(status_code: int) -> None:
    result = _classify_complete_response(
        status_code,
        b'{"status":"error","errorType":"bad_data","error":"provider-text-must-not-leak"}',
    )

    assert result == _AttemptRetryEligible(status_code=status_code)
    assert "provider-text-must-not-leak" not in repr(result)


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

    failure = _assert_safe_failure(outcome)
    assert failure.diagnostic_category == "response_too_large"
    assert closed is True
