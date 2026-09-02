"""PydanticAI translation for the bounded, framework-neutral Alert agent port."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings
from pydantic_ai.models.wrapper import WrapperModel

from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAgentRequest,
    AlertOptionalToolOutcome,
)
from app.alerts.ports import AlertOptionalToolExecutor

_TOOL_NAMES = (
    "recurrence_concentration_analysis",
    "duration_outlier_analysis",
    "reference_pattern_analysis",
)


@dataclass
class _RunState:
    """Retain per-run domain tool outcomes for framework tool responses."""

    tools: AlertOptionalToolExecutor
    tool_outcomes: dict[str, AlertOptionalToolOutcome] = field(default_factory=dict)


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
        response = await self.wrapped.request(messages, model_settings, model_request_parameters)
        await self._admit_tool_calls(response, model_request_parameters)
        return self._framework_safe_response(response, model_request_parameters)

    async def _admit_tool_calls(
        self,
        response: ModelResponse,
        model_request_parameters: ModelRequestParameters,
    ) -> None:
        output_tool_names = {tool.name for tool in model_request_parameters.output_tools}
        for part in response.parts:
            if not isinstance(part, ToolCallPart) or part.tool_name in output_tool_names:
                continue
            try:
                arguments: object = part.args_as_dict(raise_if_invalid=True)
            except (AssertionError, ValueError):
                arguments = None
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

    def __init__(self, model: Model) -> None:
        self._model = model

    async def complete(
        self, request: AlertAgentRequest, tools: AlertOptionalToolExecutor
    ) -> AlertAgentCompletion:
        """Translate one bounded Alert request through the injected model."""
        state = _RunState(tools=tools)
        agent = self._build_agent(state)
        result = await agent.run(request.model_dump_json(by_alias=True), deps=state)
        return AlertAgentCompletion.model_validate(result.output)

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
