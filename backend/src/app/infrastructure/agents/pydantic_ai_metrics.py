"""PydanticAI translation for the bounded, framework-neutral Metrics Agent port."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.usage import UsageLimits

from app.metrics.contracts import (
    MetricAgentCompletion,
    MetricAgentInsufficientRequest,
    MetricAgentOperationalFailure,
    MetricAgentOutcome,
    MetricAgentRequest,
    MetricToolOutcome,
    MetricToolRejected,
)
from app.metrics.ports import MetricToolExecutor

_TOOL_NAMES = ("spike", "oscillation", "stuck_signal")
_REQUEST_LIMIT = 4


@dataclass
class _RunState:
    tools: MetricToolExecutor | None
    tool_outcomes: dict[str, MetricToolOutcome] = field(default_factory=dict)
    model_requests: int = 0


class _PolicyObservingModel(WrapperModel):
    """Route each framework-emitted function request through the domain policy."""

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
            raise UsageLimitExceeded("Metrics Agent model request limit is four")
        self._state.model_requests += 1
        response = await self.wrapped.request(messages, model_settings, model_request_parameters)
        await self._observe_tool_calls(response, model_request_parameters)
        return response

    async def _observe_tool_calls(
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
        if self._state.tools is None:
            raise ValueError("insufficient Metrics Agent request exposes no tools")
        self._validate_tool_inputs(tool_calls)
        outcomes = await self._state.tools.execute_batch(
            tuple(tool_call.tool_name for tool_call in tool_calls)
        )
        self._state.tool_outcomes.update(
            {
                tool_call.tool_call_id: outcome
                for tool_call, outcome in zip(tool_calls, outcomes, strict=True)
            }
        )
        if any(isinstance(outcome, MetricToolRejected) for outcome in outcomes):
            raise ValueError("Metrics Agent request violated the tool request policy")

    @staticmethod
    def _validate_tool_inputs(tool_calls: tuple[ToolCallPart, ...]) -> None:
        """Reject malformed or non-empty tool input before application admission."""

        for tool_call in tool_calls:
            try:
                arguments = tool_call.args_as_dict(raise_if_invalid=True)
            except (AssertionError, ValueError) as error:
                raise ValueError("Metrics Agent tool input must be an empty object") from error
            if arguments:
                raise ValueError("Metrics Agent tools do not accept input arguments")


class PydanticAIMetricsAnalysisAgent:
    """Injected-model implementation of the framework-neutral MetricsAnalysisAgent port."""

    def __init__(
        self, model: Model, *, timeout_seconds: float = 120, max_output_tokens: int = 12_288
    ) -> None:
        """Configure one injected model with server-owned request limits."""
        self._model = model
        self._settings: ModelSettings = {
            "timeout": timeout_seconds,
            "max_tokens": max_output_tokens,
        }

    async def complete(
        self,
        request: MetricAgentRequest,
        tools: MetricToolExecutor | None = None,
    ) -> MetricAgentOutcome:
        state = _RunState(tools=tools)
        try:
            agent = self._build_agent(
                state,
                include_tools=not isinstance(request, MetricAgentInsufficientRequest)
                and tools is not None,
            )
            result = await agent.run(
                request.model_dump_json(by_alias=True),
                deps=state,
                retries=0,
                model_settings=self._settings,
                usage_limits=UsageLimits(request_limit=_REQUEST_LIMIT),
            )
            return MetricAgentCompletion.model_validate(result.output)
        except Exception:
            return MetricAgentOperationalFailure()

    def _build_agent(
        self, state: _RunState, *, include_tools: bool
    ) -> Agent[_RunState, MetricAgentCompletion]:
        agent: Agent[_RunState, MetricAgentCompletion] = Agent(
            _PolicyObservingModel(self._model, state),
            deps_type=_RunState,
            output_type=MetricAgentCompletion,
            retries=0,
            system_prompt=(
                "Complete the Metrics analysis using only the supplied structured request and "
                "registered optional tools. Return the required completion object."
            ),
        )
        if include_tools:
            self._register_tools(agent)
        return agent

    @staticmethod
    def _register_tools(agent: Agent[_RunState, MetricAgentCompletion]) -> None:
        for name in _TOOL_NAMES:
            PydanticAIMetricsAnalysisAgent._register_tool(agent, name)

    @staticmethod
    def _register_tool(agent: Agent[_RunState, MetricAgentCompletion], name: str) -> None:
        @agent.tool(name=name, description=f"Execute the registered {name} capability.", retries=0)
        async def execute_registered_tool(context: RunContext[_RunState]) -> dict[str, object]:
            outcome = context.deps.tool_outcomes.get(context.tool_call_id or "")
            if outcome is None:
                raise ValueError(
                    "framework tool call was not admitted by the Metrics request policy"
                )
            return outcome.model_dump(mode="json")
