"""Safe, application-owned operational diagnostics."""

from __future__ import annotations

import json
import logging
import math
import traceback as traceback_module
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Literal
from uuid import UUID

_LOGGER_NAME = "app.operational"
_TRACEBACK_LIMIT = 12_000
_STRING_LIMIT = 256
_REDACTION_MARKER = "[REDACTED]"

EventLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass(frozen=True, slots=True)
class DiagnosticEvent:
    """One bounded deterministic event for an operational error boundary."""

    event: str
    category: str
    level: EventLevel = "ERROR"
    observation_run_id: UUID | None = None
    lens_run_id: UUID | None = None
    lens_id: str | None = None
    source_id: str | None = None
    agent_role: str | None = None
    phase: str | None = None
    stage: str | None = None
    component: str | None = None
    model: str | None = None
    request_ordinal: int | None = None
    attempt_count: int | None = None
    duration_ms: int | None = None
    http_status: int | None = None
    observed_series_count: int | None = None
    exception_type: str | None = None


class DiagnosticObserver:
    """Observe framework-neutral deterministic diagnostic events."""

    def record(self, event: DiagnosticEvent) -> None:
        """Record an event without changing the caller's domain outcome."""


class NoOpDiagnosticObserver(DiagnosticObserver):
    """Discard deterministic diagnostic events when no trace sink is enabled."""

    def record(self, event: DiagnosticEvent) -> None:
        """Discard the supplied event."""


class OperationalEventEmitter:
    """Emit allowlisted, secret-scrubbed JSON through the application logger."""

    def __init__(
        self,
        *,
        configured_secrets: Iterable[str] = (),
        logger: logging.Logger | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._configured_secrets = tuple(
            sorted({value for value in configured_secrets if value}, key=len, reverse=True)
        )
        self._logger = logger or logging.getLogger(_LOGGER_NAME)
        self._now = now or (lambda: datetime.now(UTC))

    def emit(self, event: DiagnosticEvent, *, error: BaseException | None = None) -> None:
        """Emit one event and suppress diagnostic failures at the caller boundary."""

        try:
            payload = _event_payload(
                event,
                timestamp=self._now(),
                error=error,
                secrets=self._configured_secrets,
            )
            message = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            self._logger.log(getattr(logging, event.level), message)
        except Exception:
            # Diagnostics must never mask the original runtime result or exception.
            return


def format_safe_traceback(error: BaseException, *, configured_secrets: Iterable[str] = ()) -> str:
    """Render one bounded traceback after replacing known configured secret values."""

    rendered = "".join(traceback_module.format_exception(type(error), error, error.__traceback__))
    scrubbed = _scrub(rendered, configured_secrets)
    if len(scrubbed) <= _TRACEBACK_LIMIT:
        return scrubbed
    marker = "\n... [traceback truncated]\n"
    return f"{scrubbed[: _TRACEBACK_LIMIT - len(marker)]}{marker}"


def _event_payload(
    event: DiagnosticEvent,
    *,
    timestamp: datetime,
    error: BaseException | None,
    secrets: Iterable[str],
) -> dict[str, object]:
    values: dict[str, object | None] = {
        "timestamp": _timestamp(timestamp),
        "level": event.level.lower(),
        "event": _safe_text(event.event),
        "category": _safe_text(event.category),
        "observation_run_id": event.observation_run_id,
        "lens_run_id": event.lens_run_id,
        "lens_id": event.lens_id,
        "source_id": event.source_id,
        "agent_role": event.agent_role,
        "phase": event.phase,
        "stage": event.stage,
        "component": event.component,
        "model": event.model,
        "request_ordinal": event.request_ordinal,
        "attempt_count": event.attempt_count,
        "duration_ms": event.duration_ms,
        "http_status": event.http_status,
        "observed_series_count": event.observed_series_count,
        "exception_type": event.exception_type,
    }
    payload = {key: _scalar(value) for key, value in values.items() if value is not None}
    if error is not None:
        payload["exception_type"] = event.exception_type or type(error).__name__
        payload["traceback"] = format_safe_traceback(error, configured_secrets=secrets)
    return payload


def _timestamp(value: datetime) -> str:
    normalized = value.astimezone(UTC)
    return normalized.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _scalar(value: object) -> str | int | float:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return _scalar(value.value)
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, bool):
        raise TypeError("boolean values are not admitted to operational event fields")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise TypeError(f"unsupported operational event scalar: {type(value).__name__}")


def _safe_text(value: str) -> str:
    return value[:_STRING_LIMIT]


def _scrub(value: str, configured_secrets: Iterable[str]) -> str:
    redacted = value
    for secret in sorted({item for item in configured_secrets if item}, key=len, reverse=True):
        redacted = redacted.replace(secret, _REDACTION_MARKER)
    return redacted
