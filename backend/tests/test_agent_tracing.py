"""Focused safety and serialization tests for private development agent traces."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from app.core.diagnostics import OperationalEventEmitter
from app.infrastructure.agents.tracing import (
    AgentTraceContext,
    AgentTraceRequestMetadata,
    FileAgentTraceRecorder,
    NoOpAgentTraceRecorder,
    emit_agent_failure,
)

_RUN_ID = UUID("00000000-0000-0000-0000-000000000010")
_LENS_RUN_ID = UUID("00000000-0000-0000-0000-000000000011")
_INVOCATION_ID = UUID("00000000-0000-0000-0000-000000000012")
_NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def _context() -> AgentTraceContext:
    return AgentTraceContext(
        observation_run_id=_RUN_ID,
        lens_run_id=_LENS_RUN_ID,
        lens_id="coolant_temperature",
        agent_role="metric",
        phase="analysis",
        model="test/model",
        invocation_id=_INVOCATION_ID,
    )


def _messages(secret: str = "configured-secret") -> list[object]:
    return [
        ModelRequest(parts=[UserPromptPart(content=f"input {secret}")]),
        ModelResponse(
            parts=[TextPart(content=f"completion {secret}")],
            provider_details={"authorization": secret, "private_transport": "drop"},
        ),
    ]


def _record(recorder: FileAgentTraceRecorder, **overrides: object) -> None:
    arguments: dict[str, object] = {
        "input_json": '{"input":"configured-secret"}',
        "messages": _messages(),
        "request_metadata": (),
        "completion": {"state": "completed"},
        "terminal_state": "validated_completion",
        "started_at": _NOW,
        "finished_at": _NOW,
    }
    arguments.update(overrides)
    asyncio.run(
        recorder.record(
            _context(),
            **arguments,
        )
    )


def test_file_trace_uses_fixed_safe_per_invocation_path_and_redacts_known_secrets(tmp_path) -> None:
    """One artifact retains message parts but drops provider metadata and configured values."""
    recorder = FileAgentTraceRecorder(root=tmp_path, known_secrets=("configured-secret",))

    _record(recorder)

    path = tmp_path / str(_RUN_ID) / f"{_INVOCATION_ID}-metric-analysis.json"
    assert path.exists()
    rendered = path.read_text(encoding="utf-8")
    artifact = json.loads(rendered)
    assert artifact["trace_version"] == "1.0"
    assert artifact["invocation"]["lens_run_id"] == str(_LENS_RUN_ID)
    assert artifact["model_visible"]["messages"][0]["parts"][0]["content"] == "input [REDACTED]"
    assert "configured-secret" not in rendered
    assert "provider_details" not in rendered
    assert "private_transport" not in rendered


def test_file_trace_replaces_existing_artifact_atomically(tmp_path) -> None:
    """A completed trace file is always valid JSON after a replacement write."""
    recorder = FileAgentTraceRecorder(root=tmp_path, known_secrets=("configured-secret",))
    path = tmp_path / str(_RUN_ID) / f"{_INVOCATION_ID}-metric-analysis.json"
    path.parent.mkdir(parents=True)
    path.write_text("partial", encoding="utf-8")

    _record(recorder)

    assert json.loads(path.read_text(encoding="utf-8"))["invocation"]["terminal_state"] == (
        "validated_completion"
    )
    assert not list(path.parent.glob("*.tmp"))


def test_trace_retains_allowlisted_token_limits_and_usage_counts(tmp_path) -> None:
    """Token counts are useful diagnostics and are not credential-bearing token fields."""
    recorder = FileAgentTraceRecorder(root=tmp_path)

    _record(
        recorder,
        request_metadata=(
            AgentTraceRequestMetadata(ordinal=1, model_settings={"max_tokens": 321}),
        ),
        usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
    )

    path = tmp_path / str(_RUN_ID) / f"{_INVOCATION_ID}-metric-analysis.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert artifact["requests"][0]["model_settings"] == {"max_tokens": 321}
    assert artifact["usage"] == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}


def test_trace_failure_retains_bounded_secret_redacted_detail(tmp_path) -> None:
    """Full traces explain framework failure without preserving configured secret values."""
    recorder = FileAgentTraceRecorder(root=tmp_path, known_secrets=("configured-secret",))

    _record(recorder, failure=RuntimeError("provider rejected configured-secret"))

    path = tmp_path / str(_RUN_ID) / f"{_INVOCATION_ID}-metric-analysis.json"
    failure = json.loads(path.read_text(encoding="utf-8"))["failure"]
    assert failure == {
        "exception_type": "RuntimeError",
        "detail": "provider rejected [REDACTED]",
    }


def test_file_trace_appends_deterministic_validation_to_its_reasoning_phase(tmp_path) -> None:
    """Post-agent validation remains correlated without becoming a domain artifact field."""
    context = AgentTraceContext(
        observation_run_id=_RUN_ID,
        agent_role="observation_reasoning",
        phase="hypotheses",
        model="test/model",
        invocation_id=_INVOCATION_ID,
    )
    recorder = FileAgentTraceRecorder(root=tmp_path, known_secrets=("configured-secret",))
    asyncio.run(
        recorder.record(
            context,
            input_json="{}",
            messages=[],
            request_metadata=(),
            terminal_state="validated_completion",
            started_at=_NOW,
            finished_at=_NOW,
        )
    )

    asyncio.run(
        recorder.append_validation(
            observation_run_id=_RUN_ID,
            phase="hypotheses",
            category="hypothesis_grounding",
            outcome="rejected",
            detail="reference configured-secret is unavailable",
        )
    )

    path = tmp_path / str(_RUN_ID) / f"{_INVOCATION_ID}-observation_reasoning-hypotheses.json"
    assert json.loads(path.read_text(encoding="utf-8"))["validation_events"] == [
        {
            "category": "hypothesis_grounding",
            "outcome": "rejected",
            "detail": "reference [REDACTED] is unavailable",
        }
    ]


def test_noop_trace_recorder_never_creates_a_root(tmp_path) -> None:
    """Disabled tracing performs no filesystem work."""
    recorder = NoOpAgentTraceRecorder()

    asyncio.run(
        recorder.record(
            _context(),
            input_json="{}",
            messages=[],
            request_metadata=(),
            terminal_state="validated_completion",
            started_at=_NOW,
            finished_at=_NOW,
        )
    )

    assert list(tmp_path.iterdir()) == []


def test_invalid_path_phase_is_rejected_before_any_writer_can_use_it() -> None:
    """Only closed role/phase identifiers can influence a local artifact path."""
    with pytest.raises(ValueError, match="phase"):
        AgentTraceContext(
            observation_run_id=_RUN_ID,
            agent_role="metric",
            phase="../escape",
            model="test/model",
        )


def test_trace_write_failure_is_nonfatal_and_emits_only_safe_operational_data(tmp_path) -> None:
    """Writer failures do not escape the diagnostics path or expose model content in logs."""
    messages: list[str] = []
    logger = logging.getLogger("test.agent-trace.failure")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    recorder = _BrokenRecorder(
        root=tmp_path,
        emitter=OperationalEventEmitter(logger=logger, configured_secrets=("configured-secret",)),
    )

    _record(recorder)

    assert len(messages) == 1
    payload = json.loads(messages[0])
    assert payload["event"] == "trace_write_failed"
    assert payload["exception_type"] == "OSError"
    assert "configured-secret" not in messages[0]
    assert "completion" not in messages[0]


def test_agent_failure_events_classify_without_serializing_model_exception_content() -> None:
    """Operational agent diagnostics carry only safe category/correlation metadata."""
    messages: list[str] = []
    logger = logging.getLogger("test.agent-trace.classification")
    logger.handlers = [_CollectingHandler(messages)]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    emitter = OperationalEventEmitter(logger=logger)
    cases = (
        (TimeoutError("prompt and completion are secret-content"), "agent_timeout"),
        (
            type("UsageLimitExceeded", (Exception,), {})(
                "prompt and completion are secret-content"
            ),
            "agent_policy_rejected",
        ),
        (
            type("UnexpectedModelBehavior", (Exception,), {})(
                "prompt and completion are secret-content"
            ),
            "agent_schema_rejected",
        ),
        (
            type("ModelAPIError", (Exception,), {})("prompt and completion are secret-content"),
            "agent_provider_failed",
        ),
        (RuntimeError("prompt and completion are secret-content"), "agent_internal_failed"),
    )

    for error, category in cases:
        emit_agent_failure(emitter, _context(), error, request_ordinal=2, duration_ms=3)
        payload = json.loads(messages[-1])
        assert payload["category"] == category
        assert payload["agent_role"] == "metric"
        assert payload["request_ordinal"] == 2
        assert payload["exception_type"] == type(error).__name__
        assert isinstance(payload["duration_ms"], int)
        assert "secret-content" not in messages[-1]
        assert "traceback" not in payload


class _BrokenRecorder(FileAgentTraceRecorder):
    """Inject a deterministic local writer failure."""

    def _write_atomically(self, context: AgentTraceContext, artifact: object) -> None:
        del context, artifact
        raise OSError("configured-secret")


class _CollectingHandler(logging.Handler):
    """Collect rendered event payloads without global logging configuration."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__()
        self._messages = messages

    def emit(self, record: logging.LogRecord) -> None:
        """Store one emitted application event."""
        self._messages.append(record.getMessage())
