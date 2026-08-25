"""LangChain adapter; analytical logic remains in the shared executor."""

from __future__ import annotations

import os
from collections.abc import Iterable

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from agent_framework_experiment.agents.common import render_input, run_scripted_trajectory
from agent_framework_experiment.domain.contracts import (
    AgentRunResult,
    AlertAnalysisAgentOutput,
    AlertAnalysisInput,
    ExperimentSettings,
    ToolExecutionResult,
)
from agent_framework_experiment.domain.instructions import SYSTEM_INSTRUCTIONS
from agent_framework_experiment.tools.executor import AnalyticalToolExecutor


def build_model(settings: ExperimentSettings, *, api_key: str | None = None) -> ChatOpenAI:
    """Build OpenRouter-compatible ChatOpenAI with explicit client retry settings."""

    return ChatOpenAI(
        model=settings.model,
        api_key=api_key or os.environ.get("OPENROUTER_KEY"),
        base_url=settings.base_url,
        use_responses_api=False,
        reasoning_effort=settings.reasoning_effort,
        max_tokens=settings.max_output_tokens,
        timeout=settings.model_timeout_seconds,
        max_retries=settings.provider_retries,
        model_kwargs={"parallel_tool_calls": settings.parallel_tool_calls},
        extra_body={"provider": provider_preferences(settings)},
    )


def provider_preferences(settings: ExperimentSettings) -> dict[str, object]:
    preferences: dict[str, object] = {"allow_fallbacks": settings.allow_provider_fallbacks}
    if settings.provider_order:
        preferences["order"] = list(settings.provider_order)
    return preferences


class LangChainAlertAnalysisAgent:
    def __init__(self, settings: ExperimentSettings | None = None) -> None:
        self.settings = settings or ExperimentSettings()

    def _build_agent(self, executor: AnalyticalToolExecutor, *, api_key: str | None = None):
        @tool
        async def recurrence_concentration() -> ToolExecutionResult | dict[str, str]:
            """Analyse how strongly recurrence is concentrated across supplied alerts."""
            return await executor.invoke_from_adapter("recurrence_concentration")

        @tool
        async def duration_outlier() -> ToolExecutionResult | dict[str, str]:
            """Analyse supplied alert durations using the bounded IQR convention."""
            return await executor.invoke_from_adapter("duration_outlier")

        @tool
        async def reference_pattern_analysis() -> ToolExecutionResult | dict[str, str]:
            """Analyse supplied current/reference occurrence directions only."""
            return await executor.invoke_from_adapter("reference_pattern_analysis")

        return create_agent(
            build_model(self.settings, api_key=api_key),
            tools=(
                recurrence_concentration,
                duration_outlier,
                reference_pattern_analysis,
            ),
            system_prompt=SYSTEM_INSTRUCTIONS,
            # Tool strategy gives both frameworks the same Pydantic output contract.
            response_format=ToolStrategy(AlertAnalysisAgentOutput),
            name="langchain_alert_analysis_experiment",
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
        result = await self._build_agent(active_executor, api_key=api_key).ainvoke(
            {"messages": [{"role": "user", "content": self.render_user_input(input_data)}]}
        )
        return AgentRunResult(
            output=result["structured_response"],
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
