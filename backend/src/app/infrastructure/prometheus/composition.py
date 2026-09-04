"""Source-aware Prometheus Metric provider composition."""

from __future__ import annotations

import asyncio
import json
import math
import time
from asyncio import sleep as _async_sleep
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.settings import (
    BasicAuthCredentials,
    BearerTokenCredentials,
    PrometheusCredentials,
    PrometheusSourceSettings,
)
from app.infrastructure.prometheus.configuration import (
    _validate_prometheus_target,
    _ValidatedPrometheusTarget,
)
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricProviderScope,
    MetricSample,
    MetricSeriesAcquisitionFailure,
    MetricSeriesAcquisitionOutcome,
    MetricSeriesAcquisitionTimeout,
    MetricSeriesAvailable,
    MetricSeriesUnavailable,
)

_SOURCE_UNAVAILABLE = "prometheus_source_unavailable"
_INVALID_TARGET = "prometheus_source_invalid"
_ACQUISITION_FAILED = "prometheus_acquisition_failed"
_ACQUISITION_TIMEOUT = "prometheus_acquisition_timeout"
_MAX_RESPONSE_BYTES = 1024 * 1024
_MAX_SAMPLES = 61
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 504})
_ATTEMPT_DEADLINE_SECONDS = 15.0
_ACQUISITION_DEADLINE_SECONDS = 50.0
_RETRY_WAITS_SECONDS = (0.5, 1.0)
_PRIVATE_TRANSPORT_CAPACITY = 8


@dataclass(frozen=True)
class _ConfiguredPrometheusSource:
    """An immutable snapshot of one shared source for later transport composition."""

    id: str
    base_url: str
    credentials: PrometheusCredentials


@dataclass(frozen=True)
class _LogicalRangeQuery:
    """An immutable, private representation of one Prometheus range query."""

    url: str
    form: tuple[tuple[str, str], ...]
    headers: tuple[tuple[str, str], ...]
    auth: httpx.Auth | None


@dataclass(frozen=True)
class _AttemptAvailable:
    """A complete, valid one-attempt series result."""

    samples: tuple[MetricSample, ...]


@dataclass(frozen=True)
class _AttemptFailure:
    """A terminal one-attempt rejection with no provider detail."""


@dataclass(frozen=True)
class _AttemptTimeout:
    """A terminal one-attempt timeout classification."""


@dataclass(frozen=True)
class _AttemptRetryEligible:
    """A complete bounded response whose status may be retried by VS-03."""

    status_code: int


@dataclass(frozen=True)
class _AttemptConnectRetryEligible:
    """A connection failure that alone may enter the provider retry policy."""


_AttemptResult = (
    _AttemptAvailable
    | _AttemptFailure
    | _AttemptTimeout
    | _AttemptRetryEligible
    | _AttemptConnectRetryEligible
)


class _TransportCapacity:
    """Track finite provider-private transport work and detached cleanup."""

    def __init__(self, limit: int = _PRIVATE_TRANSPORT_CAPACITY) -> None:
        if limit < 1:
            raise ValueError("private transport capacity must be positive")
        self._limit = limit
        self._held = 0

    def try_acquire(self) -> bool:
        """Reserve one private slot without waiting."""

        if self._held >= self._limit:
            return False
        self._held += 1
        return True

    def release(self) -> None:
        """Release one slot after its acquisition lifecycle has actually terminated."""

        if self._held < 1:
            raise RuntimeError("private transport capacity was released without a lease")
        self._held -= 1


class _TransportCapacityLease:
    """Retain one acquisition slot through its lifecycle and detached cleanup."""

    def __init__(self, capacity: _TransportCapacity) -> None:
        self._capacity = capacity
        self._tracked_tasks: set[asyncio.Future[Any]] = set()
        self._lifecycle_finished = False
        self._released = False

    def track(self, task: asyncio.Future[Any]) -> None:
        """Retain the lease until one active attempt task actually terminates."""

        if self._lifecycle_finished:
            raise RuntimeError("cannot track transport work after lifecycle termination")
        self._tracked_tasks.add(task)
        task.add_done_callback(self._task_finished)

    def observe(self, task: asyncio.Future[Any]) -> None:
        """Release an already-finished task without waiting for its callback turn."""

        if task.done():
            self._task_finished(task)

    def finish(self) -> None:
        """End active acquisition ownership and release after all cleanup terminates."""

        self._lifecycle_finished = True
        self._release_if_finished()

    def _task_finished(self, task: asyncio.Future[Any]) -> None:
        self._tracked_tasks.discard(task)
        self._release_if_finished()

    def _release_if_finished(self) -> None:
        if self._lifecycle_finished and not self._tracked_tasks and not self._released:
            self._released = True
            self._capacity.release()


class PrometheusMetricSeriesProvider:
    """Resolve configured Prometheus sources behind the Metric provider port."""

    def __init__(
        self,
        sources: Iterable[PrometheusSourceSettings],
        *,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        monotonic_clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        deadline_runner: Callable[[Awaitable[Any], float], Awaitable[Any]] | None = None,
        _transport_capacity: _TransportCapacity | None = None,
    ) -> None:
        self._sources = {
            source.id: _ConfiguredPrometheusSource(
                id=source.id,
                base_url=source.base_url,
                credentials=source.credentials,
            )
            for source in sources
        }
        self._client_factory = client_factory or self._new_client
        self._monotonic_clock = monotonic_clock or time.monotonic
        self._sleep = sleep or _async_sleep
        self._deadline_runner = deadline_runner or _run_with_deadline
        self._transport_capacity = _transport_capacity or _TransportCapacity()

    async def acquire(
        self, scope: MetricProviderScope, window: MetricAnalysisWindow
    ) -> MetricSeriesAcquisitionOutcome:
        """Acquire one bounded range response for the selected configured source."""

        acquisition_deadline = self._monotonic_clock() + _ACQUISITION_DEADLINE_SECONDS
        try:
            return await self._deadline_runner(
                self._acquire_with_resilience(scope, window, acquisition_deadline),
                _ACQUISITION_DEADLINE_SECONDS,
            )
        except TimeoutError:
            return MetricSeriesAcquisitionTimeout(diagnostic=_ACQUISITION_TIMEOUT)

    async def _acquire_with_resilience(
        self,
        scope: MetricProviderScope,
        window: MetricAnalysisWindow,
        acquisition_deadline: float,
    ) -> MetricSeriesAcquisitionOutcome:
        """Resolve one source and run its immutable request through the retry policy."""

        source = self._sources.get(scope.source_id)
        if source is None:
            return MetricSeriesUnavailable(diagnostic=_SOURCE_UNAVAILABLE)
        target = _validate_prometheus_target(source.base_url)
        if target is None:
            return MetricSeriesAcquisitionFailure(diagnostic=_INVALID_TARGET)
        request = self._logical_request(source, target, scope, window)
        if not self._transport_capacity.try_acquire():
            return MetricSeriesAcquisitionFailure(diagnostic=_ACQUISITION_FAILED)

        capacity_lease = _TransportCapacityLease(self._transport_capacity)
        try:
            for attempt_number in range(3):
                attempt = await self._execute_attempt_with_deadline(request, capacity_lease)
                if isinstance(attempt, _AttemptAvailable):
                    return MetricSeriesAvailable(source="prometheus", samples=attempt.samples)
                if isinstance(attempt, _AttemptTimeout):
                    return MetricSeriesAcquisitionTimeout(diagnostic=_ACQUISITION_TIMEOUT)
                if isinstance(attempt, _AttemptFailure):
                    return MetricSeriesAcquisitionFailure(diagnostic=_ACQUISITION_FAILED)
                if attempt_number == 2:
                    return MetricSeriesAcquisitionFailure(diagnostic=_ACQUISITION_FAILED)

                retry_wait = _RETRY_WAITS_SECONDS[attempt_number]
                if acquisition_deadline - self._monotonic_clock() < (
                    retry_wait + _ATTEMPT_DEADLINE_SECONDS
                ):
                    return MetricSeriesAcquisitionTimeout(diagnostic=_ACQUISITION_TIMEOUT)
                await self._sleep(retry_wait)
        finally:
            capacity_lease.finish()

        raise AssertionError("three-attempt retry policy was not exhaustive")

    async def _execute_attempt_with_deadline(
        self,
        request: _LogicalRangeQuery,
        capacity_lease: _TransportCapacityLease,
    ) -> _AttemptResult:
        """Run and classify one complete HTTP attempt within its hard local deadline."""

        task = asyncio.ensure_future(self._execute_one_attempt(request))
        capacity_lease.track(task)
        try:
            return await self._deadline_runner(task, _ATTEMPT_DEADLINE_SECONDS)
        except TimeoutError:
            return _AttemptTimeout()
        except httpx.TimeoutException:
            return _AttemptTimeout()
        except httpx.ConnectError:
            return _AttemptConnectRetryEligible()
        except httpx.TransportError:
            return _AttemptFailure()
        except (httpx.InvalidURL, httpx.StreamError):
            return _AttemptFailure()
        except httpx.HTTPError:
            return _AttemptFailure()
        finally:
            capacity_lease.observe(task)

    @staticmethod
    def _new_client() -> httpx.AsyncClient:
        """Create the one-attempt client with ambient routing and redirects disabled."""

        return httpx.AsyncClient(
            follow_redirects=False,
            trust_env=False,
            verify=True,
            timeout=None,
        )

    @staticmethod
    def _logical_request(
        source: _ConfiguredPrometheusSource,
        target: _ValidatedPrometheusTarget,
        scope: MetricProviderScope,
        window: MetricAnalysisWindow,
    ) -> _LogicalRangeQuery:
        """Build the immutable request without changing the scope query or window."""

        start = _rfc3339_utc(window.from_)
        end = _rfc3339_utc(window.to)
        duration_seconds = math.ceil((window.to - window.from_).total_seconds())
        step_seconds = max(1, math.ceil(duration_seconds / 60))
        headers, auth = _authentication(source.credentials)
        return _LogicalRangeQuery(
            url=f"{target.origin}{target.prefix}/api/v1/query_range",
            form=(
                ("query", scope.query),
                ("start", start),
                ("end", end),
                ("step", str(step_seconds)),
                ("timeout", "10s"),
                ("limit", "2"),
            ),
            headers=tuple(headers.items()),
            auth=auth,
        )

    async def _execute_one_attempt(self, request: _LogicalRangeQuery) -> _AttemptResult:
        """Send one request, fully consume its bounded body, and classify it privately."""

        async with self._client_factory() as client:
            async with client.stream(
                "POST",
                request.url,
                data=dict(request.form),
                headers=dict(request.headers),
                auth=request.auth,
            ) as response:
                body = await _read_bounded_body(response)
                if body is None:
                    return _AttemptFailure()
                return _classify_complete_response(response.status_code, body)


async def _run_with_deadline[Result](awaitable: Awaitable[Result], seconds: float) -> Result:
    """Cancel an awaitable when its hard local monotonic deadline expires."""

    task = asyncio.ensure_future(awaitable)
    deadline = asyncio.get_running_loop().time() + seconds
    try:
        done, _ = await asyncio.wait(
            {task}, timeout=max(0.0, deadline - asyncio.get_running_loop().time())
        )
    except BaseException:
        _cancel_without_waiting(task)
        raise
    if task in done and asyncio.get_running_loop().time() < deadline:
        return task.result()

    _cancel_without_waiting(task)
    raise TimeoutError


def _cancel_without_waiting(task: asyncio.Future[Any]) -> None:
    """Signal cancellation while detached cleanup retains its private capacity lease."""

    task.cancel()
    task.add_done_callback(_consume_background_task_outcome)


def _consume_background_task_outcome(task: asyncio.Future[Any]) -> None:
    """Consume a detached cleanup outcome after it becomes state-inert."""

    try:
        task.exception()
    except BaseException:
        pass


def _authentication(
    credentials: PrometheusCredentials,
) -> tuple[dict[str, str], httpx.Auth | None]:
    """Return preemptive authentication without placing credentials in a URL."""

    if isinstance(credentials, BearerTokenCredentials):
        return {"Authorization": f"Bearer {credentials.token.get_secret_value()}"}, None
    if isinstance(credentials, BasicAuthCredentials):
        return {}, httpx.BasicAuth(credentials.username, credentials.password.get_secret_value())
    raise TypeError("unsupported Prometheus credentials")


def _rfc3339_utc(value: datetime) -> str:
    """Encode one already validated window bound as an exact UTC RFC 3339 value."""

    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


async def _read_bounded_body(response: httpx.Response) -> bytes | None:
    """Read a response completely unless its declared or streamed size exceeds 1 MiB."""

    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_RESPONSE_BYTES:
                return None
        except ValueError:
            pass
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > _MAX_RESPONSE_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _classify_complete_response(status_code: int, body: bytes) -> _AttemptResult:
    """Apply body, error-envelope, status, and success-contract precedence once."""

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None

    error_kind = _valid_error_kind(payload)
    if error_kind in {"timeout", "canceled"}:
        return _AttemptTimeout()
    if status_code in _RETRYABLE_STATUS_CODES:
        return _AttemptRetryEligible(status_code=status_code)
    if status_code < 200 or status_code >= 300:
        return _AttemptFailure()
    return _classify_success(payload)


def _valid_error_kind(payload: object) -> str | None:
    """Return a validated Prometheus error type while discarding all provider text."""

    if not isinstance(payload, dict) or payload.get("status") != "error":
        return None
    error_type = payload.get("errorType")
    error = payload.get("error")
    if not isinstance(error_type, str) or not error_type:
        return None
    if not isinstance(error, str) or not error:
        return None
    if not _valid_annotations(payload):
        return None
    return error_type


def _classify_success(payload: object) -> _AttemptResult:
    """Validate a successful matrix response and map its sole float series."""

    if not isinstance(payload, dict) or payload.get("status") != "success":
        return _AttemptFailure()
    if not _valid_annotations(payload):
        return _AttemptFailure()
    warnings = payload.get("warnings", [])
    if warnings:
        return _AttemptFailure()
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "matrix":
        return _AttemptFailure()
    result = data.get("result")
    if not isinstance(result, list):
        return _AttemptFailure()
    if not result:
        return _AttemptAvailable(samples=())
    if len(result) != 1:
        return _AttemptFailure()
    samples = _parse_float_series(result[0])
    return _AttemptFailure() if samples is None else _AttemptAvailable(samples=samples)


def _valid_annotations(payload: dict[str, Any]) -> bool:
    """Validate optional annotation arrays without retaining their text."""

    for name in ("warnings", "infos"):
        if name in payload and (
            not isinstance(payload[name], list)
            or not all(isinstance(item, str) for item in payload[name])
        ):
            return False
    return True


def _parse_float_series(series: object) -> tuple[MetricSample, ...] | None:
    """Strictly map one matrix float series without sorting or repairing samples."""

    if not isinstance(series, dict) or "histograms" in series:
        return None
    labels = series.get("metric")
    values = series.get("values")
    if (
        not isinstance(labels, dict)
        or not all(isinstance(key, str) and isinstance(value, str) for key, value in labels.items())
        or not isinstance(values, list)
        or len(values) > _MAX_SAMPLES
    ):
        return None
    samples: list[MetricSample] = []
    for pair in values:
        if not isinstance(pair, list) or len(pair) != 2:
            return None
        timestamp, value = pair
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            return None
        if not math.isfinite(timestamp) or not isinstance(value, str):
            return None
        try:
            converted_timestamp = datetime.fromtimestamp(timestamp, tz=UTC)
            converted_value = float(value)
        except (OverflowError, OSError, ValueError):
            return None
        samples.append(MetricSample(timestamp=converted_timestamp, value=converted_value))
    return tuple(samples)
