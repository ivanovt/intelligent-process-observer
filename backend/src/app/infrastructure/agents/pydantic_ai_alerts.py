"""PydanticAI translation for the bounded, framework-neutral Alert agent port."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from pydantic_ai import Agent, RunContext, capture_run_messages
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.usage import UsageLimits

from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAgentRequest,
    AlertOptionalToolOutcome,
)
from app.alerts.ports import AlertOptionalToolExecutor
from app.core.diagnostics import OperationalEventEmitter
from app.infrastructure.agents.tracing import (
    AgentTraceContext,
    AgentTraceRecorder,
    NoOpAgentTraceRecorder,
    active_trace_context,
    elapsed_duration_ms,
    emit_agent_failure,
    model_request_metadata,
    record_trace_safely,
    trace_capture_enabled,
)

_TOOL_NAMES = (
    "recurrence_concentration_analysis",
    "duration_outlier_analysis",
    "reference_pattern_analysis",
)
_REQUEST_LIMIT = 11
_TOOL_ATTEMPT_LIMIT = 10


class AlertAgentPolicyViolation(ValueError):
    """Signal a bounded Alert-agent request or tool-admission violation."""


@dataclass
class _RunState:
    """Retain per-run domain tool outcomes for framework tool responses."""

    tools: AlertOptionalToolExecutor
    tool_outcomes: dict[str, AlertOptionalToolOutcome] = field(default_factory=dict)
    model_requests: int = 0
    admitted_tool_attempts: int = 0
    trace_enabled: bool = False
    trace_requests: list[object] = field(default_factory=list)


class _DomainToolObservingModel(WrapperModel):
    """Pass every emitted framework tool request to the domain executor."""

    def __init__(self, wrapped: Model, state: _RunState) -> None:
        super().__init__(wrapped)
        self._state = state

    async def request(
        self,
        messages: list[object],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        if self._state.model_requests >= _REQUEST_LIMIT:
            raise UsageLimitExceeded("Alert Agent model request limit is eleven")
        self._state.model_requests += 1
        if self._state.trace_enabled:
            self._state.trace_requests.append(
                model_request_metadata(
                    ordinal=self._state.model_requests,
                    model_settings=model_settings,
                    model_request_parameters=model_request_parameters,
                )
            )
        response = await self.wrapped.request(messages, model_settings, model_request_parameters)
        await self._admit_tool_calls(response, model_request_parameters)
        return self._framework_safe_response(response, model_request_parameters)

    async def _admit_tool_calls(
        self,
        response: ModelResponse,
        model_request_parameters: ModelRequestParameters,
    ) -> None:
        output_tool_names = {tool.name for tool in model_request_parameters.output_tools}
        tool_calls = tuple(
            part
            for part in response.parts
            if isinstance(part, ToolCallPart) and part.tool_name not in output_tool_names
        )
        if not tool_calls:
            return
        if self._state.model_requests == _REQUEST_LIMIT:
            raise AlertAgentPolicyViolation("final Alert request cannot request a tool")
        for part in tool_calls:
            if self._state.admitted_tool_attempts >= _TOOL_ATTEMPT_LIMIT:
                raise AlertAgentPolicyViolation("Alert optional-tool attempt limit is ten")
            try:
                arguments: object = part.args_as_dict(raise_if_invalid=True)
            except (AssertionError, ValueError):
                arguments = None
            self._state.admitted_tool_attempts += 1
            self._state.tool_outcomes[part.tool_call_id] = await self._state.tools.execute(
                part.tool_name, arguments
            )

    @staticmethod
    def _framework_safe_response(
        response: ModelResponse,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Route rejected calls through a registered handler without framework retries."""
        output_tool_names = {tool.name for tool in model_request_parameters.output_tools}
        parts = tuple(
            ToolCallPart(
                part.tool_name if part.tool_name in _TOOL_NAMES else _TOOL_NAMES[0],
                {},
                part.tool_call_id,
            )
            if isinstance(part, ToolCallPart) and part.tool_name not in output_tool_names
            else part
            for part in response.parts
        )
        return replace(response, parts=list(parts))


class PydanticAIAlertAnalysisAgent:
    """Implement the Alert agent port using an injected PydanticAI model only."""

    def __init__(
        self,
        model: Model,
        *,
        timeout_seconds: float = 120,
        max_output_tokens: int = 12_288,
        model_name: str = "configured",
        trace_recorder: AgentTraceRecorder | None = None,
        emitter: OperationalEventEmitter | None = None,
    ) -> None:
        """Configure one injected model with server-owned request limits."""
        self._model = model
        self._settings: ModelSettings = {
            "timeout": timeout_seconds,
            "max_tokens": max_output_tokens,
        }
        self._model_name = model_name
        self._trace_recorder = trace_recorder or NoOpAgentTraceRecorder()
        self._emitter = emitter or OperationalEventEmitter()

    async def complete(
        self, request: AlertAgentRequest, tools: AlertOptionalToolExecutor
    ) -> AlertAgentCompletion:
        """Translate one bounded Alert request through the injected model."""
        state = _RunState(tools=tools)
        input_json = request.model_dump_json(by_alias=True)
        parent_context = active_trace_context()
        recorder: AgentTraceRecorder = (
            self._trace_recorder if parent_context is not None else NoOpAgentTraceRecorder()
        )
        context = (
            AgentTraceContext(
                observation_run_id=parent_context.observation_run_id,
                lens_run_id=parent_context.lens_run_id,
                lens_id=parent_context.lens_id,
                agent_role="alert",
                phase="analysis",
                model=self._model_name,
            )
            if parent_context is not None
            else None
        )
        trace_enabled = trace_capture_enabled(self._trace_recorder) and context is not None
        state.trace_enabled = trace_enabled
        started_at = datetime.now(UTC)
        completion: object | None = None
        failure: BaseException | None = None
        usage: object | None = None
        terminal_state = "framework_failure"
        capture = capture_run_messages() if trace_enabled else nullcontext([])
        with capture as messages:
            try:
                agent = self._build_agent(state)
                result = await agent.run(
                    input_json,
                    deps=state,
                    model_settings=self._settings,
                    usage_limits=UsageLimits(request_limit=_REQUEST_LIMIT),
                )
                completion = AlertAgentCompletion.model_validate(result.output)
                usage = result.usage
                terminal_state = "validated_completion"
                return completion
            except asyncio.CancelledError as error:
                failure = error
                terminal_state = "cancelled"
                if context is not None:
                    emit_agent_failure(
                        self._emitter,
                        context,
                        error,
                        request_ordinal=state.model_requests or None,
                        duration_ms=elapsed_duration_ms(started_at),
                    )
                raise
            except Exception as error:
                failure = error
                if context is not None:
                    emit_agent_failure(
                        self._emitter,
                        context,
                        error,
                        request_ordinal=state.model_requests or None,
                        duration_ms=elapsed_duration_ms(started_at),
                    )
                raise
            finally:
                if trace_enabled and context is not None:
                    await record_trace_safely(
                        recorder,
                        context,
                        input_json=input_json,
                        messages=messages,
                        request_metadata=tuple(state.trace_requests),
                        completion=completion,
                        failure=failure,
                        terminal_state=terminal_state,
                        started_at=started_at,
                        finished_at=datetime.now(UTC),
                        usage=usage,
                        emitter=self._emitter,
                    )

    def _build_agent(self, state: _RunState) -> Agent[_RunState, AlertAgentCompletion]:
        agent: Agent[_RunState, AlertAgentCompletion] = Agent(
            _DomainToolObservingModel(self._model, state),
            deps_type=_RunState,
            output_type=AlertAgentCompletion,
            retries=0,
            system_prompt=(
                "Analyze only the supplied Alert Lens data. Return deduplicated, merged, "
                "Lens-local descriptive findings grounded in supplied evidence. Do not infer "
                "missing data, diagnose causes, give recommendations, semantically cluster "
                "records, expand scope, use cross-Lens data, RAG, or external knowledge. "
                "Use only registered optional tools with empty-object arguments; after ten "
                "attempts, finish using available evidence."
            ),
        )
        for name in _TOOL_NAMES:
            self._register_tool(agent, name)
        return agent

    @staticmethod
    def _register_tool(agent: Agent[_RunState, AlertAgentCompletion], name: str) -> None:
        @agent.tool(name=name, description=f"Execute the registered {name} capability.", retries=0)
        async def execute_registered_tool(context: RunContext[_RunState]) -> dict[str, object]:
            outcome = context.deps.tool_outcomes.get(context.tool_call_id or "")
            if outcome is None:
                raise ValueError(
                    "framework tool call was not admitted by the Alert domain executor"
                )
            return outcome.model_dump(mode="json")
