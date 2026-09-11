"""Focused tests for the safe operational diagnostics boundary."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from app.core.diagnostics import DiagnosticEvent, OperationalEventEmitter, format_safe_traceback


def test_emitter_writes_deterministic_json_with_utc_timestamp_and_uuid_scalars() -> None:
    """Operational events retain only the fixed scalar envelope."""
    messages: list[str] = []
    logger = logging.getLogger("test.operational.deterministic")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    run_id = UUID("00000000-0000-0000-0000-000000000001")

    OperationalEventEmitter(
        logger=logger, now=lambda: datetime(2026, 9, 11, 9, 8, 7, 123456, tzinfo=UTC)
    ).emit(
        DiagnosticEvent(
            event="test_event",
            category="test_failure",
            observation_run_id=run_id,
            attempt_count=2,
            duration_ms=17,
        )
    )

    assert messages == [
        '{"attempt_count":2,"category":"test_failure","duration_ms":17,'
        '"event":"test_event","level":"error",'
        '"observation_run_id":"00000000-0000-0000-0000-000000000001",'
        '"timestamp":"2026-09-11T09:08:07.123Z"}'
    ]


def test_traceback_is_secret_scrubbed_and_preserves_exception_context() -> None:
    """Known configured values never survive a traceback rendering."""
    secret = "configured-secret-sentinel"
    try:
        raise RuntimeError(f"provider rejected {secret}")
    except RuntimeError as error:
        rendered = format_safe_traceback(error, configured_secrets=(secret,))

    assert secret not in rendered
    assert "[REDACTED]" in rendered
    assert "RuntimeError" in rendered
    assert "provider rejected" in rendered


def test_emitter_rejects_an_arbitrary_payload_value_without_logging_it() -> None:
    """A caller cannot use the emitter as an arbitrary object serialization shortcut."""
    messages: list[str] = []
    logger = logging.getLogger("test.operational.rejection")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    OperationalEventEmitter(logger=logger).emit(
        DiagnosticEvent(event="test_event", category="test_failure", lens_id=object())  # type: ignore[arg-type]
    )

    assert messages == []


def test_error_event_never_serializes_secret_or_raw_exception_outside_traceback() -> None:
    """The bounded event includes type and scrubbed traceback only."""
    messages: list[str] = []
    logger = logging.getLogger("test.operational.error")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    secret = "secret-in-error"
    try:
        raise ValueError(f"raw request with {secret}")
    except ValueError as error:
        OperationalEventEmitter(logger=logger, configured_secrets=(secret,)).emit(
            DiagnosticEvent(event="test_error", category="internal_error"), error=error
        )

    payload = json.loads(messages[0])
    assert payload["exception_type"] == "ValueError"
    assert secret not in messages[0]
    assert "raw request" in payload["traceback"]


class _CollectingHandler(logging.Handler):
    """Collect rendered log messages without a process-global logging fixture."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__()
        self._messages = messages

    def emit(self, record: logging.LogRecord) -> None:
        """Save one formatted event message."""
        self._messages.append(record.getMessage())
