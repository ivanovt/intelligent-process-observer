from __future__ import annotations

import asyncio

from agent_framework_experiment.agents.langchain import LangChainAlertAnalysisAgent
from agent_framework_experiment.agents.langchain import build_model as build_langchain_model
from agent_framework_experiment.agents.pydantic_ai import PydanticAIAlertAnalysisAgent
from agent_framework_experiment.agents.pydantic_ai import build_model as build_pydantic_model
from agent_framework_experiment.domain import (
    AlertAnalysisAgentOutput,
    AlertFinding,
    ExperimentSettings,
)
from agent_framework_experiment.fixtures.cases import (
    INSUFFICIENT_DURATION,
    RECURRENCE_CONCENTRATION,
)
from agent_framework_experiment.tools import AnalyticalToolExecutor


def test_effective_model_retry_and_request_settings_are_explicitly_disabled() -> None:
    settings = ExperimentSettings()
    pydantic_model = build_pydantic_model(settings, api_key="test")
    langchain_model = build_langchain_model(settings, api_key="test")

    assert pydantic_model.model_name == settings.model
    assert pydantic_model.provider._client.max_retries == 0
    assert pydantic_model.provider._client.timeout == 60.0
    assert langchain_model.use_responses_api is False
    assert langchain_model.max_retries == 0
    assert langchain_model.request_timeout == 60.0
    payload = langchain_model._get_request_payload([])
    assert payload["parallel_tool_calls"] is False
    assert payload["max_completion_tokens"] == 2_000
    assert payload["reasoning_effort"] == "medium"
    assert payload["extra_body"] == {"provider": {"order": ["openai"], "allow_fallbacks": False}}

    input_data = RECURRENCE_CONCENTRATION.input_data
    pydantic_agent = PydanticAIAlertAnalysisAgent(settings)._build_agent(
        AnalyticalToolExecutor(input_data), api_key="test"
    )
    langchain_agent = LangChainAlertAnalysisAgent(settings)._build_agent(
        AnalyticalToolExecutor(input_data), api_key="test"
    )
    assert pydantic_agent._max_tool_retries == 0
    assert langchain_agent.nodes["model"].retry_policy is None
    assert langchain_agent.nodes["tools"].retry_policy is None


def test_adapters_expose_the_same_three_analytical_tool_names() -> None:
    settings = ExperimentSettings()
    pydantic = PydanticAIAlertAnalysisAgent(settings)
    langchain = LangChainAlertAnalysisAgent(settings)
    input_data = RECURRENCE_CONCENTRATION.input_data

    pydantic_agent = pydantic._build_agent(
        AnalyticalToolExecutor(input_data),
        api_key="test",
    )
    langchain_agent = langchain._build_agent(
        AnalyticalToolExecutor(input_data),
        api_key="test",
    )

    expected_names = {
        "recurrence_concentration",
        "duration_outlier",
        "reference_pattern_analysis",
    }
    assert set(pydantic_agent._function_toolset.tools) == expected_names
    assert set(langchain_agent.nodes["tools"].bound._tools_by_name) == expected_names


def test_scripted_trajectories_have_exact_cross_framework_parity() -> None:
    output = AlertAnalysisAgentOutput(
        findings=(
            AlertFinding(
                id="af_1",
                statement="A-REC dominates recurrence.",
                evidence_refs=("alerts.A-REC",),
            ),
        ),
        overall_importance="moderate",
    )

    async def exercise() -> None:
        input_data = RECURRENCE_CONCENTRATION.input_data
        sequence = ("recurrence_concentration", "reference_pattern_analysis")
        pydantic_result = await PydanticAIAlertAnalysisAgent().run_scripted(
            input_data, output, sequence
        )
        langchain_result = await LangChainAlertAnalysisAgent().run_scripted(
            input_data, output, sequence
        )
        assert pydantic_result.output == langchain_result.output
        assert pydantic_result.blocked_tool_calls == langchain_result.blocked_tool_calls == 0
        assert [
            attempt.model_dump(exclude={"latency_ms"}) for attempt in pydantic_result.tool_attempts
        ] == [
            attempt.model_dump(exclude={"latency_ms"}) for attempt in langchain_result.tool_attempts
        ]

    asyncio.run(exercise())


def test_both_scripted_adapters_preserve_budget_repeats_and_normal_failures() -> None:
    output = AlertAnalysisAgentOutput(findings=(), overall_importance="low")

    async def controlled_timeout(_input):
        await asyncio.Event().wait()

    def controlled_failure(_input):
        raise RuntimeError("controlled fixture failure")

    def new_executor() -> AnalyticalToolExecutor:
        return AnalyticalToolExecutor(
            INSUFFICIENT_DURATION.input_data,
            timeout_seconds=0.001,
            handlers={
                "recurrence_concentration": controlled_failure,
                "reference_pattern_analysis": controlled_timeout,
            },
        )

    async def exercise() -> None:
        input_data = INSUFFICIENT_DURATION.input_data
        sequence = (
            "recurrence_concentration",  # failed
            "reference_pattern_analysis",  # timeout
            *("duration_outlier",) * 9,  # not_applicable, including attempt 10
        )
        pydantic_result = await PydanticAIAlertAnalysisAgent().run_scripted(
            input_data, output, sequence, executor=new_executor()
        )
        langchain_result = await LangChainAlertAnalysisAgent().run_scripted(
            input_data, output, sequence, executor=new_executor()
        )
        for result in (pydantic_result, langchain_result):
            assert len(result.tool_attempts) == 10
            assert result.tool_attempts[-1].invocation_order == 10
            assert result.blocked_tool_calls == 1
            assert [attempt.status for attempt in result.tool_attempts[:3]] == [
                "failed",
                "timeout",
                "not_applicable",
            ]
            assert result.tool_attempts[-1].status == "not_applicable"
        assert [
            attempt.model_dump(exclude={"latency_ms"}) for attempt in pydantic_result.tool_attempts
        ] == [
            attempt.model_dump(exclude={"latency_ms"}) for attempt in langchain_result.tool_attempts
        ]

    asyncio.run(exercise())
