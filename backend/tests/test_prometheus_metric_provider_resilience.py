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
    _cancel_without_waiting,
    _LogicalRangeQuery,
    _TransportCapacity,
    _TransportCapacityLease,
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


def _deadline_after(signal: asyncio.Event, deadline_seconds: float):
    async def runner(awaitable: Any, seconds: float) -> Any:
        if seconds != deadline_seconds:
            return await awaitable
        task = asyncio.ensure_future(awaitable)
        await signal.wait()
        _cancel_without_waiting(task)
        raise TimeoutError

    return runner


def test_httpx_default_timeout_is_disabled_and_system_attempt_deadline_is_authoritative() -> None:
    async def scenario() -> None:
        default_client = httpx.AsyncClient()
        production_client = PrometheusMetricSeriesProvider._new_client()
        try:
            assert default_client.timeout == httpx.Timeout(5.0)
            assert production_client.timeout == httpx.Timeout(None)
        finally:
            await default_client.aclose()
            await production_client.aclose()

        attempt_started = asyncio.Event()
        provider = PrometheusMetricSeriesProvider(
            [_source()], deadline_runner=_deadline_after(attempt_started, 15.0)
        )

        async def longer_than_httpx_default(_: _LogicalRangeQuery) -> object:
            attempt_started.set()
            await asyncio.Event().wait()

        provider._execute_one_attempt = longer_than_httpx_default  # type: ignore[method-assign]

        assert await provider.acquire(_scope(), _window()) == MetricSeriesAcquisitionTimeout(
            diagnostic="prometheus_acquisition_timeout"
        )

    asyncio.run(scenario())


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
@pytest.mark.parametrize(
    ("retry_two_anchor", "expected_type", "expected_requests", "expected_waits"),
    [
        (34.000_001, MetricSeriesAcquisitionTimeout, 2, [0.5]),
        (34.0, MetricSeriesAvailable, 3, [0.5, 1.0]),
    ],
)
def test_second_retry_admission_uses_an_inclusive_one_second_plus_attempt_boundary(
    retry_kind: str | int,
    retry_two_anchor: float,
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
        if requests == 2:
            clock.value = retry_two_anchor
        if requests == 3 and retry_two_anchor == 34.0:
            return httpx.Response(200, json=_success())
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

    assert isinstance(outcome, expected_type)
    assert requests == expected_requests
    assert waits == expected_waits


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

    async def classify() -> object:
        capacity = _TransportCapacity()
        assert capacity.try_acquire()
        lease = _TransportCapacityLease(capacity)
        try:
            return await provider._execute_attempt_with_deadline(
                _LogicalRangeQuery(url="https://example.test", form=(), headers=(), auth=None),
                lease,
            )
        finally:
            lease.finish()

    result = asyncio.run(classify())

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
        self.closing_started = asyncio.Event()
        self.close_release = asyncio.Event()
        self._stream = stream

    async def __aenter__(self) -> _ClosingClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        self.closing_started.set()
        await self.close_release.wait()
        self.closed = True

    @asynccontextmanager
    async def stream(self, *_: object, **__: object):
        response = httpx.Response(200, stream=self._stream)
        try:
            yield response
        finally:
            await response.aclose()


def test_attempt_deadline_cancels_body_and_closes_response_and_client() -> None:
    async def scenario() -> None:
        stream = _HangingStream()
        client = _ClosingClient(stream)

        provider = PrometheusMetricSeriesProvider(
            [_source()],
            client_factory=lambda: client,
            deadline_runner=_deadline_after(stream.started, 15.0),
        )
        acquire = asyncio.create_task(provider.acquire(_scope(), _window()))
        await asyncio.wait_for(client.closing_started.wait(), timeout=0.1)

        assert stream.cancelled is True
        assert stream.closed is True
        assert client.closed is False
        assert acquire.done() is True

        assert acquire.result() == MetricSeriesAcquisitionTimeout(
            diagnostic="prometheus_acquisition_timeout"
        )

        client.close_release.set()
        await asyncio.sleep(0)
        assert client.closed is True

    asyncio.run(scenario())


def test_deadline_returns_before_resistant_cleanup_and_releases_capacity_afterward() -> None:
    async def scenario() -> None:
        stream = _HangingStream()
        client = _ClosingClient(stream)
        capacity = _TransportCapacity(limit=1)
        client_constructions = 0

        def blocked_client_factory() -> _ClosingClient:
            nonlocal client_constructions
            client_constructions += 1
            return client

        provider = PrometheusMetricSeriesProvider(
            [_source()],
            client_factory=blocked_client_factory,
            deadline_runner=_deadline_after(stream.started, 15.0),
            _transport_capacity=capacity,
        )
        first = asyncio.create_task(provider.acquire(_scope(), _window()))
        await asyncio.wait_for(client.closing_started.wait(), timeout=0.1)

        assert await asyncio.wait_for(first, timeout=0.1) == MetricSeriesAcquisitionTimeout(
            diagnostic="prometheus_acquisition_timeout"
        )
        assert stream.cancelled is True
        assert stream.closed is True
        assert client.closed is False
        assert client_constructions == 1

        saturated = await provider.acquire(_scope(), _window())
        assert saturated == MetricSeriesAcquisitionFailure(
            diagnostic="prometheus_acquisition_failed"
        )
        assert client_constructions == 1

        client.close_release.set()
        for _ in range(10):
            await asyncio.sleep(0)
            if client.closed:
                break
        assert client.closed is True
        await asyncio.sleep(0)

        successful_requests = 0

        def success_client_factory() -> httpx.AsyncClient:
            nonlocal successful_requests

            def handler(_: httpx.Request) -> httpx.Response:
                nonlocal successful_requests
                successful_requests += 1
                return httpx.Response(200, json=_success())

            return httpx.AsyncClient(transport=httpx.MockTransport(handler))

        provider._client_factory = success_client_factory
        provider._deadline_runner = _immediate_deadline
        assert await provider.acquire(_scope(), _window()) == MetricSeriesAvailable(
            source="prometheus", samples=()
        )
        assert successful_requests == 1

    asyncio.run(scenario())


def test_active_transport_capacity_saturation_rejects_before_client_or_request() -> None:
    class ActiveStream(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.closed = False

        async def __aiter__(self):
            self.started.set()
            await self.release.wait()
            yield b'{"status":"success","data":{"resultType":"matrix","result":[]}}'

        async def aclose(self) -> None:
            self.closed = True

    async def scenario() -> None:
        stream = ActiveStream()
        capacity = _TransportCapacity(limit=1)
        active_client_constructions = 0
        active_requests = 0
        rejected_client_constructions = 0

        def active_client_factory() -> httpx.AsyncClient:
            nonlocal active_client_constructions
            active_client_constructions += 1

            def active_handler(_: httpx.Request) -> httpx.Response:
                nonlocal active_requests
                active_requests += 1
                return httpx.Response(200, stream=stream)

            return httpx.AsyncClient(transport=httpx.MockTransport(active_handler))

        def fail_on_client_construction() -> httpx.AsyncClient:
            nonlocal rejected_client_constructions
            rejected_client_constructions += 1
            raise AssertionError("saturated acquisition constructed a client")

        provider = PrometheusMetricSeriesProvider(
            [_source()],
            client_factory=active_client_factory,
            deadline_runner=_immediate_deadline,
            _transport_capacity=capacity,
        )
        active = asyncio.create_task(provider.acquire(_scope(), _window()))
        await asyncio.wait_for(stream.started.wait(), timeout=0.1)

        provider._client_factory = fail_on_client_construction
        saturated = await provider.acquire(_scope(), _window())
        assert saturated == MetricSeriesAcquisitionFailure(
            diagnostic="prometheus_acquisition_failed"
        )
        assert active_client_constructions == 1
        assert active_requests == 1
        assert rejected_client_constructions == 0

        stream.release.set()
        assert await asyncio.wait_for(active, timeout=0.1) == MetricSeriesAvailable(
            source="prometheus", samples=()
        )
        assert stream.closed is True

        released_requests = 0

        def released_client_factory() -> httpx.AsyncClient:
            def released_handler(_: httpx.Request) -> httpx.Response:
                nonlocal released_requests
                released_requests += 1
                return httpx.Response(200, json=_success())

            return httpx.AsyncClient(transport=httpx.MockTransport(released_handler))

        provider._client_factory = released_client_factory
        assert await provider.acquire(_scope(), _window()) == MetricSeriesAvailable(
            source="prometheus", samples=()
        )
        assert released_requests == 1

    asyncio.run(scenario())


def test_capacity_is_held_during_retry_wait_and_later_admitted_attempt() -> None:
    class RetryStream(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def __aiter__(self):
            self.started.set()
            await self.release.wait()
            yield b'{"status":"success","data":{"resultType":"matrix","result":[]}}'

    async def scenario() -> None:
        retry_sleep_started = asyncio.Event()
        retry_sleep_release = asyncio.Event()
        retry_stream = RetryStream()
        capacity = _TransportCapacity(limit=1)
        client_constructions = 0
        requests = 0

        def client_factory() -> httpx.AsyncClient:
            nonlocal client_constructions
            client_constructions += 1

            def handler(_: httpx.Request) -> httpx.Response:
                nonlocal requests
                requests += 1
                if requests == 1:
                    return httpx.Response(500, content=b"not-json")
                if requests == 2:
                    return httpx.Response(200, stream=retry_stream)
                return httpx.Response(200, json=_success())

            return httpx.AsyncClient(transport=httpx.MockTransport(handler))

        async def blocked_retry_sleep(seconds: float) -> None:
            assert seconds == 0.5
            retry_sleep_started.set()
            await retry_sleep_release.wait()

        provider = PrometheusMetricSeriesProvider(
            [_source()],
            client_factory=client_factory,
            sleep=blocked_retry_sleep,
            deadline_runner=_immediate_deadline,
            _transport_capacity=capacity,
        )
        retrying = asyncio.create_task(provider.acquire(_scope(), _window()))
        await asyncio.wait_for(retry_sleep_started.wait(), timeout=0.1)

        assert await provider.acquire(_scope(), _window()) == MetricSeriesAcquisitionFailure(
            diagnostic="prometheus_acquisition_failed"
        )
        assert client_constructions == 1
        assert requests == 1

        retry_sleep_release.set()
        await asyncio.wait_for(retry_stream.started.wait(), timeout=0.1)
        assert await provider.acquire(_scope(), _window()) == MetricSeriesAcquisitionFailure(
            diagnostic="prometheus_acquisition_failed"
        )
        assert client_constructions == 2
        assert requests == 2

        retry_stream.release.set()
        assert await asyncio.wait_for(retrying, timeout=0.1) == MetricSeriesAvailable(
            source="prometheus", samples=()
        )

        assert await provider.acquire(_scope(), _window()) == MetricSeriesAvailable(
            source="prometheus", samples=()
        )
        assert client_constructions == 3
        assert requests == 3

    asyncio.run(scenario())


def test_acquisition_cleanup_retains_capacity_after_deadline_during_retry_wait() -> None:
    async def scenario() -> None:
        retry_sleep_started = asyncio.Event()
        cleanup_started = asyncio.Event()
        cleanup_release = asyncio.Event()
        cleanup_finished = asyncio.Event()
        capacity = _TransportCapacity(limit=1)
        client_constructions = 0
        requests = 0

        def client_factory() -> httpx.AsyncClient:
            nonlocal client_constructions
            client_constructions += 1

            def handler(_: httpx.Request) -> httpx.Response:
                nonlocal requests
                requests += 1
                if requests == 1:
                    return httpx.Response(500, content=b"not-json")
                return httpx.Response(200, json=_success())

            return httpx.AsyncClient(transport=httpx.MockTransport(handler))

        async def resistant_retry_sleep(_: float) -> None:
            retry_sleep_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cleanup_started.set()
                await cleanup_release.wait()
                cleanup_finished.set()
                raise

        provider = PrometheusMetricSeriesProvider(
            [_source()],
            client_factory=client_factory,
            sleep=resistant_retry_sleep,
            deadline_runner=_deadline_after(retry_sleep_started, 50.0),
            _transport_capacity=capacity,
        )

        assert await provider.acquire(_scope(), _window()) == MetricSeriesAcquisitionTimeout(
            diagnostic="prometheus_acquisition_timeout"
        )
        await asyncio.wait_for(cleanup_started.wait(), timeout=0.1)

        provider._deadline_runner = _immediate_deadline
        assert await provider.acquire(_scope(), _window()) == MetricSeriesAcquisitionFailure(
            diagnostic="prometheus_acquisition_failed"
        )
        assert client_constructions == 1
        assert requests == 1

        cleanup_release.set()
        await asyncio.wait_for(cleanup_finished.wait(), timeout=0.1)
        await asyncio.sleep(0)

        assert await provider.acquire(_scope(), _window()) == MetricSeriesAvailable(
            source="prometheus", samples=()
        )
        assert client_constructions == 2
        assert requests == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("late_kind", ["available", "connect_error"])
def test_timeout_discards_late_attempt_outcomes_without_retrying(late_kind: str) -> None:
    async def scenario() -> None:
        cleanup_started = asyncio.Event()
        cleanup_release = asyncio.Event()
        cleanup_finished = asyncio.Event()
        attempt_started = asyncio.Event()
        calls = 0
        waits: list[float] = []

        provider = PrometheusMetricSeriesProvider(
            [_source()], deadline_runner=_deadline_after(attempt_started, 15.0)
        )

        async def delayed_attempt(_: _LogicalRangeQuery) -> object:
            nonlocal calls
            calls += 1
            attempt_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cleanup_started.set()
                await cleanup_release.wait()
                cleanup_finished.set()
                if late_kind == "connect_error":
                    raise httpx.ConnectError("late connect error") from None
                return _AttemptAvailable(samples=())

        async def sleep(seconds: float) -> None:
            waits.append(seconds)

        provider._execute_one_attempt = delayed_attempt  # type: ignore[method-assign]
        provider._sleep = sleep

        outcome = await provider.acquire(_scope(), _window())
        await asyncio.wait_for(cleanup_started.wait(), timeout=0.1)
        assert outcome == MetricSeriesAcquisitionTimeout(
            diagnostic="prometheus_acquisition_timeout"
        )
        assert calls == 1
        assert waits == []

        cleanup_release.set()
        await asyncio.wait_for(cleanup_finished.wait(), timeout=0.1)
        await asyncio.sleep(0)
        assert calls == 1
        assert waits == []

    asyncio.run(scenario())


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

    provider = PrometheusMetricSeriesProvider(
        [_source()],
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        sleep=hanging_sleep,
        deadline_runner=_deadline_after(sleeps_started, 50.0),
    )
    outcome = asyncio.run(provider.acquire(_scope(), _window()))

    assert outcome == MetricSeriesAcquisitionTimeout(diagnostic="prometheus_acquisition_timeout")
    assert sleeps_started.is_set()
    assert sleeps_cancelled is True
    assert requests == 1


def test_hard_local_deadline_wins_when_cancelled_work_raises_connect_error() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        finished = asyncio.Event()

        async def race() -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError as error:
                finished.set()
                raise httpx.ConnectError("racing connect error") from error

        task = asyncio.create_task(race())
        await started.wait()
        _cancel_without_waiting(task)
        await finished.wait()
        await asyncio.sleep(0)

    asyncio.run(scenario())


def test_hard_deadline_returns_without_waiting_for_delayed_cancellation_cleanup() -> None:
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

        task = asyncio.create_task(delayed_cleanup())
        await asyncio.sleep(0)
        _cancel_without_waiting(task)
        try:
            await asyncio.wait_for(cleanup_started.wait(), timeout=0.1)
            assert task.done() is False
            assert cleanup_finished.is_set() is False
            cleanup_release.set()
            await asyncio.wait_for(cleanup_finished.wait(), timeout=0.1)
        finally:
            cleanup_release.set()

    asyncio.run(scenario())
