"""Private, fail-open development artifacts for PydanticAI invocations."""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic_ai.messages import ModelMessagesTypeAdapter

from app.core.diagnostics import DiagnosticEvent, OperationalEventEmitter

_TRACE_VERSION = "1.0"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
_SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
_SENSITIVE_KEY = re.compile(
    r"(?:^|_)(?:authorization|credential(?:s)?|cookie(?:s)?|header(?:s)?|password|secret(?:s)?|"
    r"api_key|access_token|refresh_token|id_token|bearer_token)(?:$|_)",
    re.I,
)
_OMITTED_PROVIDER_KEYS = frozenset(
    {
        "metadata",
        "provider_details",
        "provider_metadata",
        "provider_response",
        "provider_response_id",
        "response_headers",
    }
)
_ACTIVE_TRACE_CONTEXT: ContextVar[AgentTraceContext | None] = ContextVar(
    "active_agent_trace_context", default=None
)


def default_agent_trace_root() -> Path:
    """Return the fixed ignored development trace root."""
    return _REPOSITORY_ROOT / "tmp" / "agent-traces"


@dataclass(frozen=True, slots=True)
class AgentTraceContext:
    """Safe identity and phase metadata for one model invocation artifact."""

    observation_run_id: UUID
    agent_role: Literal["metric", "alert", "observation_reasoning", "report"]
    phase: str
    model: str
    lens_run_id: UUID | None = None
    lens_id: str | None = None
    invocation_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Reject path-affecting values outside the closed identifier vocabulary."""
        if _SAFE_IDENTIFIER.fullmatch(self.phase) is None:
            raise ValueError("trace phase must be a lowercase underscore identifier")
        if self.lens_id is not None and not self.lens_id:
            raise ValueError("trace lens_id must be non-empty when supplied")
        if not self.model:
            raise ValueError("trace model must be non-empty")


@contextmanager
def activate_trace_context(context: AgentTraceContext):
    """Make one infrastructure trace identity available without changing a domain port."""
    token: Token[AgentTraceContext | None] = _ACTIVE_TRACE_CONTEXT.set(context)
    try:
        yield
    finally:
        _ACTIVE_TRACE_CONTEXT.reset(token)


def active_trace_context() -> AgentTraceContext | None:
    """Return the invocation context propagated by the owning application boundary."""
    return _ACTIVE_TRACE_CONTEXT.get()


@dataclass(frozen=True, slots=True)
class AgentTraceRequestMetadata:
    """Allowlisted model request metadata captured by adapter wrapper models."""

    ordinal: int
    model_settings: Mapping[str, object] | None
    function_tools: tuple[Mapping[str, object], ...] = ()
    output_tools: tuple[Mapping[str, object], ...] = ()


class AgentTraceRecorder(Protocol):
    """Persist an invocation artifact without affecting the agent's result."""

    async def record(
        self,
        context: AgentTraceContext,
        *,
        input_json: str,
        messages: list[object],
        request_metadata: tuple[AgentTraceRequestMetadata, ...],
        raw_responses: tuple[object, ...] = (),
        completion: object | None = None,
        failure: BaseException | None = None,
        terminal_state: str,
        started_at: datetime,
        finished_at: datetime,
        usage: object | None = None,
        validation_events: tuple[Mapping[str, object], ...] = (),
    ) -> None:
        """Record the available invocation state on a fail-open diagnostic path."""

    async def append_validation(
        self,
        *,
        observation_run_id: UUID,
        phase: str,
        category: str,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        """Append one safe deterministic validation outcome when capture is enabled."""


class NoOpAgentTraceRecorder:
    """Disabled recorder that creates no directories and retains no trace state."""

    async def record(self, context: AgentTraceContext, **_: object) -> None:
        """Discard a trace while preserving the caller's execution semantics."""
        del context

    async def append_validation(
        self,
        *,
        observation_run_id: UUID,
        phase: str,
        category: str,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        """Discard deterministic validation metadata while tracing is disabled."""
        del observation_run_id, phase, category, outcome, detail


class FileAgentTraceRecorder:
    """Write sensitive per-invocation JSON artifacts through atomic replacement."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        known_secrets: Iterable[str] = (),
        emitter: OperationalEventEmitter | None = None,
    ) -> None:
        """Configure the fixed trace root and non-empty configured secret sentinels."""
        self._root = (root or default_agent_trace_root()).resolve()
        values = {value for value in known_secrets if value}
        self._known_secrets = tuple(sorted(values, key=len, reverse=True))
        self._emitter = emitter or OperationalEventEmitter(configured_secrets=self._known_secrets)

    @property
    def root(self) -> Path:
        """Return the local artifact root for development inspection only."""
        return self._root

    async def record(
        self,
        context: AgentTraceContext,
        *,
        input_json: str,
        messages: list[object],
        request_metadata: tuple[AgentTraceRequestMetadata, ...],
        raw_responses: tuple[object, ...] = (),
        completion: object | None = None,
        failure: BaseException | None = None,
        terminal_state: str,
        started_at: datetime,
        finished_at: datetime,
        usage: object | None = None,
        validation_events: tuple[Mapping[str, object], ...] = (),
    ) -> None:
        """Serialize atomically; diagnostic failures are deliberately non-fatal."""
        try:
            artifact = _artifact(
                context=context,
                input_json=input_json,
                messages=messages,
                raw_responses=raw_responses,
                request_metadata=request_metadata,
                completion=completion,
                failure=failure,
                terminal_state=terminal_state,
                started_at=started_at,
                finished_at=finished_at,
                usage=usage,
                validation_events=validation_events,
                secrets=self._known_secrets,
            )
            await asyncio.to_thread(self._write_atomically, context, artifact)
        except Exception as error:  # Diagnostics must not replace the original outcome.
            self._emitter.emit(
                DiagnosticEvent(
                    event="trace_write_failed",
                    category="trace_write_failed",
                    observation_run_id=context.observation_run_id,
                    lens_run_id=context.lens_run_id,
                    lens_id=context.lens_id,
                    agent_role=context.agent_role,
                    phase=context.phase,
                    model=context.model,
                ),
                error=error,
            )

    def _write_atomically(self, context: AgentTraceContext, artifact: Mapping[str, object]) -> None:
        path = self._path_for(context)
        self._write_path_atomically(path, artifact, invocation_id=str(context.invocation_id))

    @staticmethod
    def _write_path_atomically(
        path: Path, artifact: Mapping[str, object], *, invocation_id: str
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{invocation_id}-", suffix=".tmp", dir=path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    async def append_validation(
        self,
        *,
        observation_run_id: UUID,
        phase: str,
        category: str,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        """Append a safe deterministic outcome to its one reasoning/report invocation."""
        try:
            await asyncio.to_thread(
                self._append_validation,
                observation_run_id,
                phase,
                category,
                outcome,
                detail,
            )
        except Exception as error:
            self._emitter.emit(
                DiagnosticEvent(
                    event="trace_write_failed",
                    category="trace_write_failed",
                    observation_run_id=observation_run_id,
                    agent_role="observation_reasoning" if phase != "report_render" else "report",
                    phase=phase,
                ),
                error=error,
            )

    def _append_validation(
        self,
        observation_run_id: UUID,
        phase: str,
        category: str,
        outcome: str,
        detail: str | None,
    ) -> None:
        role = "report" if phase == "report_render" else "observation_reasoning"
        invocation_phase = "generation" if role == "report" else phase
        candidates = sorted(
            (self._root / str(observation_run_id)).glob(f"*-{role}-{invocation_phase}.json")
        )
        if len(candidates) != 1:
            return
        path = candidates[0]
        artifact = json.loads(path.read_text(encoding="utf-8"))
        events = artifact.setdefault("validation_events", [])
        if not isinstance(events, list):
            raise ValueError("trace validation_events must be a list")
        event_values: dict[str, str] = {"category": category, "outcome": outcome}
        safe_detail = _bounded_detail(detail)
        if safe_detail is not None:
            event_values["detail"] = safe_detail
        event = _redact(event_values, self._known_secrets)
        events.append(event)
        redacted_artifact = _redact(artifact, self._known_secrets)
        self._write_path_atomically(path, redacted_artifact, invocation_id="validation")

    def _path_for(self, context: AgentTraceContext) -> Path:
        # UUIDs and closed role/phase values are the only path components from runtime state.
        return (
            self._root
            / str(context.observation_run_id)
            / (f"{context.invocation_id}-{context.agent_role}-{context.phase}.json")
        )


def build_agent_trace_recorder(
    *,
    enabled: bool,
    known_secrets: Iterable[str] = (),
    root: Path | None = None,
    emitter: OperationalEventEmitter | None = None,
) -> AgentTraceRecorder:
    """Select a no-op recorder unless explicitly enabled by trusted composition."""
    if not enabled:
        return NoOpAgentTraceRecorder()
    return FileAgentTraceRecorder(root=root, known_secrets=known_secrets, emitter=emitter)


def trace_capture_enabled(recorder: AgentTraceRecorder) -> bool:
    """Return whether the recorder is allowed to retain full interaction content."""
    return isinstance(recorder, FileAgentTraceRecorder)


def elapsed_duration_ms(started_at: datetime, *, finished_at: datetime | None = None) -> int:
    """Return a non-negative UTC elapsed duration suitable for an operational event."""
    finished_at = finished_at or datetime.now(UTC)
    return max(0, round((finished_at - started_at).total_seconds() * 1000))


async def record_trace_safely(
    recorder: AgentTraceRecorder,
    context: AgentTraceContext,
    *,
    emitter: OperationalEventEmitter | None = None,
    **kwargs: object,
) -> None:
    """Protect application behavior from an injected recorder implementation failure."""
    try:
        await recorder.record(context, **kwargs)
    except Exception as error:
        (emitter or OperationalEventEmitter()).emit(
            DiagnosticEvent(
                event="trace_write_failed",
                category="trace_write_failed",
                observation_run_id=context.observation_run_id,
                lens_run_id=context.lens_run_id,
                lens_id=context.lens_id,
                agent_role=context.agent_role,
                phase=context.phase,
                model=context.model,
            ),
            error=error,
        )


def model_request_metadata(
    *, ordinal: int, model_settings: object, model_request_parameters: object
) -> AgentTraceRequestMetadata:
    """Project PydanticAI request definitions through an explicit safe allowlist."""
    return AgentTraceRequestMetadata(
        ordinal=ordinal,
        model_settings=_safe_model_settings(model_settings),
        function_tools=_tool_definitions(getattr(model_request_parameters, "function_tools", ())),
        output_tools=_tool_definitions(getattr(model_request_parameters, "output_tools", ())),
    )


def emit_agent_failure(
    emitter: OperationalEventEmitter,
    context: AgentTraceContext,
    error: BaseException,
    *,
    request_ordinal: int | None = None,
    duration_ms: int | None = None,
) -> None:
    """Emit a safe classified agent-boundary failure without model-visible content."""
    category = _failure_category(error)
    event = DiagnosticEvent(
        event="agent_invocation_failed",
        category=category,
        observation_run_id=context.observation_run_id,
        lens_run_id=context.lens_run_id,
        lens_id=context.lens_id,
        agent_role=context.agent_role,
        phase=context.phase,
        model=context.model,
        request_ordinal=request_ordinal,
        duration_ms=duration_ms,
        exception_type=type(error).__name__,
    )
    # Agent failures are normalized runtime outcomes.  Their exception messages can include
    # provider/model content, so operational logs deliberately retain only safe metadata.
    emitter.emit(event)


def _failure_category(error: BaseException) -> str:
    name = type(error).__name__
    if isinstance(error, TimeoutError) or name == "APITimeoutError":
        return "agent_timeout"
    if name in {"UsageLimitExceeded", "ReasoningPolicyViolation", "ReportPolicyViolation"}:
        return "agent_policy_rejected"
    if name in {"UnexpectedModelBehavior", "ValidationError"}:
        return "agent_schema_rejected"
    if name == "ModelAPIError":
        return "agent_provider_failed"
    return "agent_internal_failed"


def _artifact(
    *,
    context: AgentTraceContext,
    input_json: str,
    messages: list[object],
    raw_responses: tuple[object, ...],
    request_metadata: tuple[AgentTraceRequestMetadata, ...],
    completion: object | None,
    failure: BaseException | None,
    terminal_state: str,
    started_at: datetime,
    finished_at: datetime,
    usage: object | None,
    validation_events: tuple[Mapping[str, object], ...],
    secrets: tuple[str, ...],
) -> dict[str, object]:
    serialized_messages = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
    serialized_raw_responses = ModelMessagesTypeAdapter.dump_python(
        list(raw_responses), mode="json"
    )
    return _redact(
        {
            "trace_version": _TRACE_VERSION,
            "invocation": {
                "invocation_id": str(context.invocation_id),
                "observation_run_id": str(context.observation_run_id),
                "lens_run_id": str(context.lens_run_id) if context.lens_run_id else None,
                "lens_id": context.lens_id,
                "agent_role": context.agent_role,
                "phase": context.phase,
                "model": context.model,
                "started_at": _utc(started_at),
                "finished_at": _utc(finished_at),
                "duration_ms": elapsed_duration_ms(started_at, finished_at=finished_at),
                "terminal_state": terminal_state,
            },
            "model_visible": {"input": input_json, "messages": serialized_messages},
            "raw_model_responses": serialized_raw_responses,
            "requests": [asdict(item) for item in request_metadata],
            "completion": _json_value(completion) if completion is not None else None,
            "failure": _failure(failure, secrets=secrets),
            "usage": _json_value(usage) if usage is not None else None,
            "validation_events": [_json_value(event) for event in validation_events],
        },
        secrets,
    )


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _failure(error: BaseException | None, *, secrets: tuple[str, ...]) -> dict[str, str] | None:
    if error is None:
        return None
    return {
        "exception_type": type(error).__name__,
        "detail": _bounded_detail(str(error), secrets=secrets),
    }


def _bounded_detail(value: str | None, *, secrets: tuple[str, ...] = ()) -> str | None:
    """Retain a small diagnostic explanation after replacing known configured secrets."""
    if value is None:
        return None
    for secret in secrets:
        value = value.replace(secret, "[REDACTED]")
    return value[:512]


def _safe_model_settings(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return {
        key: _json_value(value[key])
        for key in ("timeout", "max_tokens", "temperature")
        if key in value
    }


def _tool_definitions(values: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(values, (tuple, list)):
        return ()
    definitions: list[Mapping[str, object]] = []
    for tool in values:
        name = getattr(tool, "name", None)
        parameters = getattr(tool, "parameters_json_schema", None)
        if isinstance(name, str):
            definitions.append(
                {
                    "name": name,
                    "parameters_json_schema": _json_value(parameters) if parameters else {},
                }
            )
    return tuple(definitions)


def _json_value(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "asdict"):
        return value.asdict()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _redact(value: object, secrets: tuple[str, ...], *, key: str | None = None) -> object:
    if key in _OMITTED_PROVIDER_KEYS or (key is not None and _SENSITIVE_KEY.search(key)):
        return None
    if isinstance(value, Mapping):
        return {
            str(item_key): _redact(item, secrets, key=str(item_key))
            for item_key, item in value.items()
            if str(item_key) not in _OMITTED_PROVIDER_KEYS
            and _SENSITIVE_KEY.search(str(item_key)) is None
        }
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
    return value
