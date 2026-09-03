"""Source-aware Prometheus Metric provider composition."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable
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


_AttemptResult = _AttemptAvailable | _AttemptFailure | _AttemptTimeout | _AttemptRetryEligible


class PrometheusMetricSeriesProvider:
    """Resolve configured Prometheus sources behind the Metric provider port."""

    def __init__(
        self,
        sources: Iterable[PrometheusSourceSettings],
        *,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
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

    async def acquire(
        self, scope: MetricProviderScope, window: MetricAnalysisWindow
    ) -> MetricSeriesAcquisitionOutcome:
        """Acquire one bounded range response for the selected configured source."""

        source = self._sources.get(scope.source_id)
        if source is None:
            return MetricSeriesUnavailable(diagnostic=_SOURCE_UNAVAILABLE)
        target = _validate_prometheus_target(source.base_url)
        if target is None:
            return MetricSeriesAcquisitionFailure(diagnostic=_INVALID_TARGET)
        request = self._logical_request(source, target, scope, window)
        attempt = await self._execute_one_attempt(request)
        if isinstance(attempt, _AttemptAvailable):
            return MetricSeriesAvailable(source="prometheus", samples=attempt.samples)
        if isinstance(attempt, _AttemptTimeout):
            return MetricSeriesAcquisitionTimeout(diagnostic=_ACQUISITION_TIMEOUT)
        # Retry admission and the second/third attempts are deliberately VS-03 work.
        return MetricSeriesAcquisitionFailure(diagnostic=_ACQUISITION_FAILED)

    @staticmethod
    def _new_client() -> httpx.AsyncClient:
        """Create the one-attempt client with ambient routing and redirects disabled."""

        return httpx.AsyncClient(follow_redirects=False, trust_env=False, verify=True)

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

        try:
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
        # VS-03 supplies the ordered HTTPX exception/deadline/retry policy.  This
        # temporary single-attempt boundary only makes unexpected client failures safe.
        except httpx.HTTPError:
            return _AttemptFailure()


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
