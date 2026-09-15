"""Focused tests for the safe operational diagnostics boundary."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.core.diagnostics import DiagnosticEvent, OperationalEventEmitter, format_safe_traceback
from app.core.settings import Settings


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


def test_emitter_includes_only_bounded_retrieval_decision_counts() -> None:
    """Curated retrieval diagnostics retain aggregate strategy data without content."""
    messages: list[str] = []
    logger = logging.getLogger("test.operational.retrieval-decision")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    run_id = UUID("00000000-0000-0000-0000-000000000001")

    OperationalEventEmitter(
        logger=logger, now=lambda: datetime(2026, 9, 11, 9, 8, 7, tzinfo=UTC)
    ).emit(
        DiagnosticEvent(
            event="knowledge_retrieval_decision",
            category="relaxed_admitted",
            level="INFO",
            observation_run_id=run_id,
            agent_role="observation_reasoning",
            phase="hypotheses",
            component="curated_knowledge_retrieval",
            strict_candidate_count=64,
            strict_admitted_count=0,
            relaxed_candidate_count=3,
            relaxed_admitted_count=1,
            returned_passage_count=1,
        )
    )

    payload = json.loads(messages[0])
    assert payload == {
        "agent_role": "observation_reasoning",
        "category": "relaxed_admitted",
        "component": "curated_knowledge_retrieval",
        "event": "knowledge_retrieval_decision",
        "level": "info",
        "observation_run_id": "00000000-0000-0000-0000-000000000001",
        "phase": "hypotheses",
        "relaxed_admitted_count": 1,
        "relaxed_candidate_count": 3,
        "returned_passage_count": 1,
        "strict_admitted_count": 0,
        "strict_candidate_count": 64,
        "timestamp": "2026-09-11T09:08:07.000Z",
    }
    assert not {
        "query",
        "content",
        "passage",
        "source",
        "score",
        "distance",
        "embedding",
        "credential",
    }.intersection(payload)


def test_emitter_omits_unevaluated_retrieval_path_counts() -> None:
    """Strict decisions do not imply that a relaxed search ran."""
    messages: list[str] = []
    logger = logging.getLogger("test.operational.retrieval-omission")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    OperationalEventEmitter(logger=logger).emit(
        DiagnosticEvent(
            event="curated_knowledge_retrieval_completed",
            category="strict_admitted",
            level="INFO",
            strict_candidate_count=1,
            strict_admitted_count=1,
            returned_passage_count=1,
        )
    )

    payload = json.loads(messages[0])
    assert "relaxed_candidate_count" not in payload
    assert "relaxed_admitted_count" not in payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("strict_candidate_count", 64),
        ("strict_admitted_count", 64),
        ("relaxed_candidate_count", 32),
        ("relaxed_admitted_count", 32),
        ("returned_passage_count", 4),
    ],
)
def test_emitter_accepts_retrieval_count_boundaries(field: str, value: int) -> None:
    """Each controlled retrieval count retains its documented inclusive upper bound."""
    messages: list[str] = []
    logger = logging.getLogger(f"test.operational.retrieval-boundary.{field}")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    OperationalEventEmitter(logger=logger).emit(
        DiagnosticEvent(
            event="curated_knowledge_retrieval_completed",
            category="no_match",
            **{field: value},  # type: ignore[arg-type]
        )
    )

    assert json.loads(messages[0])[field] == value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("strict_candidate_count", -1),
        ("strict_candidate_count", 65),
        ("strict_admitted_count", 65),
        ("relaxed_candidate_count", True),
        ("relaxed_admitted_count", 33),
        ("returned_passage_count", 5),
        ("returned_passage_count", True),
    ],
)
def test_emitter_safely_omits_invalid_retrieval_counts(field: str, value: object) -> None:
    """Invalid retrieval aggregates cannot turn diagnostics into an arbitrary log channel."""
    messages: list[str] = []
    logger = logging.getLogger(f"test.operational.retrieval-invalid.{field}.{value}")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    OperationalEventEmitter(logger=logger).emit(
        DiagnosticEvent(
            event="curated_knowledge_retrieval_completed",
            category="no_match",
            **{field: value},  # type: ignore[arg-type]
        )
    )

    assert messages == []


def test_traceback_preserves_stack_and_type_without_exception_message_content() -> None:
    """Operational traceback rendering cannot serialize arbitrary exception text."""
    secret = "configured-secret-sentinel"
    try:
        raise RuntimeError(f"provider rejected {secret}")
    except RuntimeError as error:
        rendered = format_safe_traceback(error, configured_secrets=(secret,))

    assert secret not in rendered
    assert "RuntimeError" in rendered
    assert "provider rejected" not in rendered
    assert "test_traceback_preserves_stack" in rendered


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


def test_error_event_never_serializes_secret_or_arbitrary_exception_content() -> None:
    """The bounded event includes type and stack location without exception text."""
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
    assert "raw request" not in payload["traceback"]
    assert "ValueError" in payload["traceback"]


def test_database_url_password_is_included_in_secret_redaction_without_logging_its_url() -> None:
    """Database credentials are available to diagnostics without admitting a URL field."""
    password = "database-password-sentinel"
    database_url = f"postgresql+psycopg://reader:{password}@db.example.invalid:5432/ipo"
    settings = Settings(_env_file=None, database_url=database_url)
    messages: list[str] = []
    logger = logging.getLogger("test.operational.database-password")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    try:
        raise RuntimeError(f"database connection failed: {database_url}")
    except RuntimeError as error:
        OperationalEventEmitter(
            logger=logger, configured_secrets=settings.configured_secret_values()
        ).emit(
            DiagnosticEvent(event="database_failure", category="persistence_failure"), error=error
        )

    assert password in settings.configured_secret_values()
    assert password not in messages[0]
    assert database_url not in messages[0]


class _CollectingHandler(logging.Handler):
    """Collect rendered log messages without a process-global logging fixture."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__()
        self._messages = messages

    def emit(self, record: logging.LogRecord) -> None:
        """Save one formatted event message."""
        self._messages.append(record.getMessage())
