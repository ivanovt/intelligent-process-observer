"""PydanticAI adapter; analytical logic remains in the shared executor."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings

from agent_framework_experiment.agents.common import render_input, run_scripted_trajectory
from agent_framework_experiment.domain.contracts import (
    AgentRunResult,
    AlertAnalysisAgentOutput,
    AlertAnalysisInput,
    ExperimentSettings,
    ToolExecutionResult,
)
from agent_framework_experiment.domain.instructions import SYSTEM_INSTRUCTIONS
from agent_framework_experiment.shared.openrouter import (
    build_pydantic_openrouter_model,
    provider_preferences,
)
from agent_framework_experiment.tools.executor import AnalyticalToolExecutor


def build_model(settings: ExperimentSettings, *, api_key: str | None = None) -> OpenAIChatModel:
    """Build the OpenRouter-compatible Chat Completions client with no retries."""

    return build_pydantic_openrouter_model(settings, api_key=api_key)


class PydanticAIAlertAnalysisAgent:
    def __init__(self, settings: ExperimentSettings | None = None) -> None:
        self.settings = settings or ExperimentSettings()

    def _build_agent(
        self, executor: AnalyticalToolExecutor, *, api_key: str | None = None
    ) -> Agent[None, AlertAnalysisAgentOutput]:
        async def recurrence_concentration() -> ToolExecutionResult | dict[str, str]:
            """Analyse how strongly recurrence is concentrated across supplied alerts."""
            return await executor.invoke_from_adapter("recurrence_concentration")

        async def duration_outlier() -> ToolExecutionResult | dict[str, str]:
            """Analyse supplied alert durations using the bounded IQR convention."""
            return await executor.invoke_from_adapter("duration_outlier")

        async def reference_pattern_analysis() -> ToolExecutionResult | dict[str, str]:
            """Analyse supplied current/reference occurrence directions only."""
            return await executor.invoke_from_adapter("reference_pattern_analysis")

        return Agent(
            build_model(self.settings, api_key=api_key),
            output_type=AlertAnalysisAgentOutput,
            instructions=SYSTEM_INSTRUCTIONS,
            model_settings=OpenAIChatModelSettings(
                max_tokens=self.settings.max_output_tokens,
                parallel_tool_calls=self.settings.parallel_tool_calls,
                openai_reasoning_effort=self.settings.reasoning_effort,
                extra_body={"provider": provider_preferences(self.settings)},
            ),
            retries=self.settings.framework_retries,
            tool_timeout=self.settings.analytical_tool_timeout_seconds,
            tools=(
                recurrence_concentration,
                duration_outlier,
                reference_pattern_analysis,
            ),
        )

    @staticmethod
    def render_user_input(input_data: AlertAnalysisInput) -> str:
        """Use the common canonical input and experiment-local evidence catalog."""

        return render_input(input_data)

    async def analyze(
        self,
        input_data: AlertAnalysisInput,
        *,
        api_key: str | None = None,
        executor: AnalyticalToolExecutor | None = None,
    ) -> AgentRunResult:
        active_executor = executor or AnalyticalToolExecutor(
            input_data,
            timeout_seconds=self.settings.analytical_tool_timeout_seconds,
        )
        result = await self._build_agent(active_executor, api_key=api_key).run(
            self.render_user_input(input_data)
        )
        return AgentRunResult(
            output=result.output,
            tool_attempts=active_executor.traces,
            available_evidence_ids=active_executor.available_evidence_ids,
            blocked_tool_calls=active_executor.blocked_tool_calls,
        )

    async def run_scripted(
        self,
        input_data: AlertAnalysisInput,
        output: AlertAnalysisAgentOutput,
        tool_sequence: Iterable[str],
        *,
        executor: AnalyticalToolExecutor | None = None,
    ) -> AgentRunResult:
        return await run_scripted_trajectory(input_data, output, tool_sequence, executor=executor)
