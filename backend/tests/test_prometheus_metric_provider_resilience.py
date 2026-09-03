"""VS-03 resilience tests for the production Prometheus Metric provider."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.core.settings import BearerTokenCredentials, PrometheusSourceSettings
from app.infrastructure.prometheus.composition import (
    PrometheusMetricSeriesProvider,
    _AttemptAvailable,
    _AttemptConnectRetryEligible,
    _AttemptFailure,
    _AttemptRetryEligible,
    _AttemptTimeout,
    _LogicalRangeQuery,
    _run_with_deadline,
)
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricProviderScope,
    MetricSeriesAcquisitionFailure,
    MetricSeriesAcquisitionTimeout,
    MetricSeriesAvailable,
)

_START = datetime(2026, 9, 1, 12, tzinfo=UTC)


def _source() -> PrometheusSourceSettings:
    return PrometheusSourceSettings(
        id="plant-prometheus",
        name="Plant Prometheus",
        base_url="https://prometheus.example.test/prometheus",
        credentials=BearerTokenCredentials(type="bearer_token", token="retry-secret"),
    )


def _scope() -> MetricProviderScope:
    return MetricProviderScope(
        adapter_type="prometheus", source_id="plant-prometheus", query="up{job='plant'}"
    )


def _window() -> MetricAnalysisWindow:
    return MetricAnalysisWindow(**{"from": _START, "to": _START + timedelta(minutes=1)})


def _success() -> dict[str, Any]:
    return {"status": "success", "data": {"resultType": "matrix", "result": []}}


class _Clock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


async def _immediate_deadline(awaitable: Any, _: float) -> Any:
    return await awaitable


@pytest.mark.parametrize("retry_kind", ["connect", 429, 500, 502, 504])
@pytest.mark.parametrize(
    ("terminal_attempt", "expected_count", "expected_waits"),
    [(1, 1, []), (2, 2, [0.5]), (3, 3, [0.5, 1.0]), (None, 3, [0.5, 1.0])],
)
def test_retry_attempt_count_waits_and_logical_request_identity(
    retry_kind: str | int,
    terminal_attempt: int | None,
    expected_count: int,
    expected_waits: list[float],
) -> None:
    requests: list[httpx.Request] = []
    waits: list[float] = []
    invocation = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal invocation
        invocation += 1
        requests.append(request)
        if terminal_attempt == invocation:
            return httpx.Response(200, json=_success())
        if retry_kind == "connect":
            raise httpx.ConnectError("unavailable", request=request)
        return httpx.Response(retry_kind, headers={"retry-after": "999"}, content=b"not-json")

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    provider = PrometheusMetricSeriesProvider(
        [_source()],
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        sleep=sleep,
    )

    outcome = asyncio.run(provider.acquire(_scope(), _window()))

    if terminal_attempt is None:
        assert outcome == MetricSeriesAcquisitionFailure(diagnostic="prometheus_acquisition_failed")
    else:
        assert outcome == MetricSeriesAvailable(source="prometheus", samples=())
    assert len(requests) == expected_count
    assert waits == expected_waits
    snapshots = [
        (request.method, str(request.url), request.content, request.headers["authorization"])
        for request in requests
    ]
    assert snapshots == [snapshots[0]] * expected_count


@pytest.mark.parametrize("retry_kind", ["connect", 429, 500, 502, 504])
@pytest.mark.parametrize(
    ("clock_value", "expected_type", "expected_requests", "expected_waits"),
    [
        (34.500_001, MetricSeriesAcquisitionTimeout, 1, []),
        (34.5, MetricSeriesAvailable, 2, [0.5]),
    ],
)
def test_first_retry_admission_has_an_inclusive_wait_plus_attempt_boundary(
    retry_kind: str | int,
    clock_value: float,
    expected_type: type[object],
    expected_requests: int,
    expected_waits: list[float],
) -> None:
    clock = _Clock()
    waits: list[float] = []
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            clock.value = clock_value
            if retry_kind == "connect":
                raise httpx.ConnectError("unavailable", request=request)
            return httpx.Response(retry_kind, content=b"not-json")
        return httpx.Response(200, json=_success())

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    provider = PrometheusMetricSeriesProvider(
        [_source()],
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        monotonic_clock=clock,
        sleep=sleep,
        deadline_runner=_immediate_deadline,
    )

    outcome = asyncio.run(provider.acquire(_scope(), _window()))

    assert isinstance(outcome, expected_type)
    assert requests == expected_requests
    assert waits == expected_waits


@pytest.mark.parametrize(
    ("pre_transport_elapsed", "expected_type", "expected_requests", "expected_waits"),
    [
        (34.500_001, MetricSeriesAcquisitionTimeout, 1, []),
        (34.5, MetricSeriesAvailable, 2, [0.5]),
    ],
)
def test_acquisition_budget_anchor_includes_pre_transport_work(
    pre_transport_elapsed: float,
    expected_type: type[object],
    expected_requests: int,
    expected_waits: list[float],
) -> None:
    clock = _Clock()
    waits: list[float] = []
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            raise httpx.ConnectError("unavailable", request=request)
        return httpx.Response(200, json=_success())

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    provider = PrometheusMetricSeriesProvider(
        [_source()],
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        monotonic_clock=clock,
        sleep=sleep,
        deadline_runner=_immediate_deadline,
    )
    logical_request = provider._logical_request

    def delayed_logical_request(*args: object) -> _LogicalRangeQuery:
        clock.value = pre_transport_elapsed
        return logical_request(*args)  # type: ignore[arg-type]

    provider._logical_request = delayed_logical_request  # type: ignore[method-assign]

    outcome = asyncio.run(provider.acquire(_scope(), _window()))

    assert isinstance(outcome, expected_type)
    assert requests == expected_requests
    assert waits == expected_waits


@pytest.mark.parametrize("retry_kind", ["connect", 429, 500, 502, 504])
def test_second_retry_admission_uses_its_exact_one_second_wait(retry_kind: str | int) -> None:
    clock = _Clock()
    waits: list[float] = []
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 2:
            clock.value = 34.000_001
        if retry_kind == "connect":
            raise httpx.ConnectError("unavailable", request=request)
        return httpx.Response(retry_kind, content=b"not-json")

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    provider = PrometheusMetricSeriesProvider(
        [_source()],
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        monotonic_clock=clock,
        sleep=sleep,
        deadline_runner=_immediate_deadline,
    )

    outcome = asyncio.run(provider.acquire(_scope(), _window()))

    assert outcome == MetricSeriesAcquisitionTimeout(diagnostic="prometheus_acquisition_timeout")
    assert requests == 2
    assert waits == [0.5]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ConnectTimeout("timeout"), _AttemptTimeout),
        (httpx.ReadTimeout("timeout"), _AttemptTimeout),
        (httpx.WriteTimeout("timeout"), _AttemptTimeout),
        (httpx.PoolTimeout("timeout"), _AttemptTimeout),
        (httpx.ConnectError("connect"), _AttemptConnectRetryEligible),
        (httpx.ReadError("read"), _AttemptFailure),
        (httpx.WriteError("write"), _AttemptFailure),
        (httpx.CloseError("close"), _AttemptFailure),
        (httpx.RemoteProtocolError("remote"), _AttemptFailure),
        (httpx.LocalProtocolError("local"), _AttemptFailure),
        (httpx.ProxyError("proxy"), _AttemptFailure),
        (httpx.UnsupportedProtocol("unsupported"), _AttemptFailure),
        (httpx.DecodingError("decode"), _AttemptFailure),
        (httpx.TooManyRedirects("redirect"), _AttemptFailure),
        (httpx.RequestError("generic request error"), _AttemptFailure),
        (
            httpx.HTTPStatusError(
                "raised status error",
                request=httpx.Request("GET", "https://prometheus.example.test"),
                response=httpx.Response(500),
            ),
            _AttemptFailure,
        ),
        (httpx.InvalidURL("invalid"), _AttemptFailure),
        (httpx.StreamError("stream"), _AttemptFailure),
    ],
)
def test_httpx_exception_taxonomy_has_only_one_retryable_exception(
    error: Exception, expected: type[object]
) -> None:
    provider = PrometheusMetricSeriesProvider([_source()], deadline_runner=_immediate_deadline)

    async def raise_error(_: _LogicalRangeQuery) -> object:
        raise error

    provider._execute_one_attempt = raise_error  # type: ignore[method-assign]
    result = asyncio.run(
        provider._execute_attempt_with_deadline(
            _LogicalRangeQuery(url="https://example.test", form=(), headers=(), auth=None)
        )
    )

    assert isinstance(result, expected)


@pytest.mark.parametrize(
    "error",
    [
        httpx.RequestError("generic request error"),
        httpx.HTTPStatusError(
            "raised status error",
            request=httpx.Request("GET", "https://prometheus.example.test"),
            response=httpx.Response(500),
        ),
    ],
)
def test_generic_httpx_errors_return_typed_failure_without_retry(error: Exception) -> None:
    async def scenario() -> tuple[object, list[float], int]:
        waits: list[float] = []
        calls = 0
        provider = PrometheusMetricSeriesProvider([_source()], deadline_runner=_immediate_deadline)

        async def raise_error(_: _LogicalRangeQuery) -> object:
            nonlocal calls
            calls += 1
            raise error

        async def sleep(seconds: float) -> None:
            waits.append(seconds)

        provider._execute_one_attempt = raise_error  # type: ignore[method-assign]
        provider._sleep = sleep
        return await provider.acquire(_scope(), _window()), waits, calls

    outcome, waits, calls = asyncio.run(scenario())

    assert outcome == MetricSeriesAcquisitionFailure(diagnostic="prometheus_acquisition_failed")
    assert waits == []
    assert calls == 1


def test_terminal_attempt_variants_never_sleep_or_retry() -> None:
    async def run_terminal(result: object) -> tuple[object, list[float], int]:
        waits: list[float] = []
        calls = 0
        provider = PrometheusMetricSeriesProvider(
            [_source()],
            sleep=lambda seconds: waits.append(seconds),  # type: ignore[arg-type]
        )

        async def execute(_: _LogicalRangeQuery) -> object:
            nonlocal calls
            calls += 1
            return result

        provider._execute_one_attempt = execute  # type: ignore[method-assign]
        provider._deadline_runner = _immediate_deadline
        outcome = await provider.acquire(_scope(), _window())
        return outcome, waits, calls

    for result, expected in (
        (_AttemptFailure(), MetricSeriesAcquisitionFailure),
        (_AttemptTimeout(), MetricSeriesAcquisitionTimeout),
        (_AttemptAvailable(samples=()), MetricSeriesAvailable),
    ):
        outcome, waits, calls = asyncio.run(run_terminal(result))
        assert isinstance(outcome, expected)
        assert waits == []
        assert calls == 1


def test_retry_exhaustion_is_failure_after_three_executed_eligible_results() -> None:
    async def scenario() -> tuple[object, list[float], int]:
        waits: list[float] = []
        calls = 0
        provider = PrometheusMetricSeriesProvider([_source()], deadline_runner=_immediate_deadline)

        async def execute(_: _LogicalRangeQuery) -> object:
            nonlocal calls
            calls += 1
            return _AttemptRetryEligible(status_code=500)

        async def sleep(seconds: float) -> None:
            waits.append(seconds)

        provider._execute_one_attempt = execute  # type: ignore[method-assign]
        provider._sleep = sleep
        return await provider.acquire(_scope(), _window()), waits, calls

    outcome, waits, calls = asyncio.run(scenario())
    assert outcome == MetricSeriesAcquisitionFailure(diagnostic="prometheus_acquisition_failed")
    assert calls == 3
    assert waits == [0.5, 1.0]


class _HangingStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.cancelled = False
        self.closed = False
        self.started = asyncio.Event()
        self._never = asyncio.Event()

    async def __aiter__(self):
        self.started.set()
        try:
            await self._never.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        yield b"unreachable"

    async def aclose(self) -> None:
        self.closed = True


class _ClosingClient:
    def __init__(self, stream: _HangingStream) -> None:
        self.closed = False
        self._stream = stream

    async def __aenter__(self) -> _ClosingClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        self.closed = True

    @asynccontextmanager
    async def stream(self, *_: object, **__: object):
        response = httpx.Response(200, stream=self._stream)
        try:
            yield response
        finally:
            await response.aclose()


def test_attempt_deadline_cancels_body_and_closes_response_and_client() -> None:
    stream = _HangingStream()
    client = _ClosingClient(stream)

    async def short_deadline(awaitable: Any, seconds: float) -> Any:
        return await _run_with_deadline(awaitable, 0.01 if seconds == 15.0 else 1.0)

    provider = PrometheusMetricSeriesProvider(
        [_source()], client_factory=lambda: client, deadline_runner=short_deadline
    )
    outcome = asyncio.run(provider.acquire(_scope(), _window()))

    assert outcome == MetricSeriesAcquisitionTimeout(diagnostic="prometheus_acquisition_timeout")
    assert stream.cancelled is True
    assert stream.closed is True
    assert client.closed is True


def test_acquisition_deadline_cancels_a_retry_wait_without_another_attempt() -> None:
    sleeps_started = asyncio.Event()
    sleeps_cancelled = False
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500, content=b"not-json")

    async def hanging_sleep(_: float) -> None:
        nonlocal sleeps_cancelled
        sleeps_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            sleeps_cancelled = True
            raise

    async def short_deadline(awaitable: Any, seconds: float) -> Any:
        return await _run_with_deadline(awaitable, 0.01 if seconds == 50.0 else 1.0)

    provider = PrometheusMetricSeriesProvider(
        [_source()],
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        sleep=hanging_sleep,
        deadline_runner=short_deadline,
    )
    outcome = asyncio.run(provider.acquire(_scope(), _window()))

    assert outcome == MetricSeriesAcquisitionTimeout(diagnostic="prometheus_acquisition_timeout")
    assert sleeps_started.is_set()
    assert sleeps_cancelled is True
    assert requests == 1


def test_hard_local_deadline_wins_when_cancelled_work_raises_connect_error() -> None:
    async def race() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError as error:
            raise httpx.ConnectError("racing connect error") from error

    with pytest.raises(TimeoutError):
        asyncio.run(_run_with_deadline(race(), 0.01))


def test_hard_deadline_return_does_not_wait_for_delayed_cancellation_cleanup() -> None:
    async def scenario() -> None:
        cleanup_started = asyncio.Event()
        cleanup_release = asyncio.Event()
        cleanup_finished = asyncio.Event()

        async def delayed_cleanup() -> None:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cleanup_started.set()
                await cleanup_release.wait()
                cleanup_finished.set()
                raise

        runner = asyncio.create_task(_run_with_deadline(delayed_cleanup(), 0.005))
        try:
            await asyncio.wait_for(cleanup_started.wait(), timeout=0.1)
            done, _ = await asyncio.wait({runner}, timeout=0.02)
            assert runner in done
            with pytest.raises(TimeoutError):
                await runner
            assert cleanup_finished.is_set() is False
        finally:
            cleanup_release.set()
            await asyncio.wait_for(cleanup_finished.wait(), timeout=0.1)

    asyncio.run(scenario())
