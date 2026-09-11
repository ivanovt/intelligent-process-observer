from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.infrastructure.agents.pydantic_ai_metrics import PydanticAIMetricsAnalysisAgent
from app.infrastructure.agents.tracing import FileAgentTraceRecorder
from app.metrics.contracts import (
    MetricAgentCompletion,
    MetricAgentInsufficientRequest,
    MetricAgentOperationalFailure,
    MetricAgentUsableRequest,
    MetricAnalysisWindow,
    MetricEvidence,
    MetricIdentity,
    MetricSample,
    MetricSemantics,
    MetricToolRejected,
    MetricTrend,
    MetricVariability,
    PreparedGoodSeries,
)
from app.metrics.tools import MetricToolRegistry

START = datetime(2026, 8, 30, tzinfo=UTC)


def run(coroutine):
    return asyncio.run(coroutine)


def usable_request(*, data_quality: str = "good") -> MetricAgentUsableRequest:
    identity = MetricIdentity(
        observation_id=uuid4(),
        observation_run_id=uuid4(),
        lens_id="coolant-temperature",
        lens_run_id=uuid4(),
        metric_ref="coolant_temperature",
        unit="celsius",
    )
    window = MetricAnalysisWindow(**{"from": START, "to": START + timedelta(minutes=3)})
    return MetricAgentUsableRequest(
        identity=identity,
        analysis_window=window,
        analysis_objectives=("spike", "drift"),
        data_quality=data_quality,
        evidence=MetricEvidence(mean=20.0, std=1.0, min=10.0, max=30.0, slope=0.1),
        semantics=MetricSemantics(
            trend=MetricTrend(direction="increasing", rate="moderate"),
            variability=MetricVariability(state="low"),
        ),
        allowed_tools=MetricToolRegistry.descriptors,
        dataset_ref="opaque-run-dataset",
    )


def insufficient_request() -> MetricAgentInsufficientRequest:
    request = usable_request()
    return MetricAgentInsufficientRequest(
        identity=request.identity,
        analysis_window=request.analysis_window,
        data_quality="insufficient",
    )


def tool_registry() -> MetricToolRegistry:
    values = (10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0)
    return MetricToolRegistry(
        "opaque-run-dataset",
        PreparedGoodSeries(
            data_quality="good",
            samples=tuple(
                MetricSample(timestamp=START + timedelta(seconds=index), value=value)
                for index, value in enumerate(values)
            ),
            evidence=MetricEvidence(
                mean=sum(values) / len(values),
                std=0.0,
                min=min(values),
                max=max(values),
                slope=0.0,
            ),
            residuals=(0.0,) * len(values),
        ),
    )


def completion(info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"state": "completed"})])


def function_model(
    responses: list[Callable[[AgentInfo], ModelResponse]],
) -> tuple[FunctionModel, list[tuple[object, AgentInfo]]]:
    calls: list[tuple[object, AgentInfo]] = []

    def scripted(messages, info: AgentInfo) -> ModelResponse:
        calls.append((messages, info))
        return responses[len(calls) - 1](info)

    return FunctionModel(scripted), calls


def user_prompt(messages: object) -> str:
    for message in messages:
        for part in message.parts:
            if part.part_kind == "user-prompt":
                return part.content
    raise AssertionError("FunctionModel did not receive the serialized agent request")


def system_prompt(messages: object) -> str:
    """Extract server-owned instructions from a function-model request."""
    return " ".join(
        " ".join(part.content.split())
        for message in messages
        for part in message.parts
        if part.part_kind == "system-prompt"
    )


def test_adapter_preserves_usable_projections_and_zero_tool_completion() -> None:
    for data_quality in ("good", "degraded"):
        model, calls = function_model([completion])
        request = usable_request(data_quality=data_quality)

        outcome = run(PydanticAIMetricsAnalysisAgent(model).complete(request, tool_registry()))

        assert outcome == MetricAgentCompletion()
        assert len(calls) == 1
        messages, info = calls[0]
        assert [tool.name for tool in info.function_tools] == [
            "spike",
            "oscillation",
            "stuck_signal",
        ]
        prompt = user_prompt(messages)
        assert request.model_dump_json(by_alias=True) == prompt
        assert "prometheus" not in prompt
        assert "query" not in prompt
        assert "reference_periods" not in prompt
        assert "history" not in prompt


def test_adapter_routes_each_serial_tool_call_through_the_existing_registry() -> None:
    model, calls = function_model(
        [
            lambda _: ModelResponse(parts=[ToolCallPart("spike", {})]),
            lambda _: ModelResponse(parts=[ToolCallPart("oscillation", {})]),
            lambda _: ModelResponse(parts=[ToolCallPart("stuck_signal", {})]),
            completion,
        ]
    )
    registry = tool_registry()

    outcome = run(PydanticAIMetricsAnalysisAgent(model).complete(usable_request(), registry))

    assert outcome == MetricAgentCompletion()
    assert len(calls) == 4
    ledger = [
        (entry.requested_name, entry.executed, entry.consumed_slot) for entry in registry.ledger
    ]
    assert ledger == [
        ("spike", True, True),
        ("oscillation", True, True),
        ("stuck_signal", True, True),
    ]


def test_usable_metric_guidance_descriptions_and_settings_steer_every_tool_request() -> None:
    """Tool-enabled requests retain server-owned sequential steering through continuations."""
    model, calls = function_model(
        [lambda _: ModelResponse(parts=[ToolCallPart("spike", {})]), completion]
    )

    assert run(
        PydanticAIMetricsAnalysisAgent(model).complete(usable_request(), tool_registry())
    ) == (MetricAgentCompletion())
    assert len(calls) == 2
    instructions = system_prompt(calls[0][0]).lower()
    for clause in (
        "immutable structured metric request",
        "empty object (`{}`)",
        "at most one optional tool",
        "wait for its result",
        "at most once",
        "at most three tool attempts",
        "strict required completion object",
    ):
        assert clause in instructions
    descriptions = {tool.name: tool.description for tool in calls[0][1].function_tools}
    assert descriptions == {
        "spike": "Inspect the supplied immutable Metric evidence for abrupt spike behavior.",
        "oscillation": "Inspect the supplied immutable Metric evidence for oscillating behavior.",
        "stuck_signal": "Inspect the supplied immutable Metric evidence for a stuck signal.",
    }
    for _, info in calls:
        assert info.model_settings == {
            "timeout": 120,
            "max_tokens": 12_288,
            "parallel_tool_calls": False,
        }


def test_adapter_routes_duplicate_parallel_unregistered_and_fourth_requests_to_policy() -> None:
    cases = {
        "duplicate": (
            [
                lambda _: ModelResponse(parts=[ToolCallPart("spike", {})]),
                lambda _: ModelResponse(parts=[ToolCallPart("spike", {})]),
                completion,
            ],
            2,
        ),
        "parallel": (
            [
                lambda _: ModelResponse(
                    parts=[ToolCallPart("spike", {}), ToolCallPart("oscillation", {})]
                ),
                completion,
            ],
            1,
        ),
        "unregistered": (
            [lambda _: ModelResponse(parts=[ToolCallPart("drift", {})]), completion],
            1,
        ),
        "over_budget": (
            [
                lambda _: ModelResponse(parts=[ToolCallPart("spike", {})]),
                lambda _: ModelResponse(parts=[ToolCallPart("oscillation", {})]),
                lambda _: ModelResponse(parts=[ToolCallPart("stuck_signal", {})]),
                lambda _: ModelResponse(parts=[ToolCallPart("spike", {})]),
                completion,
            ],
            4,
        ),
    }
    for reason, (responses, expected_request_count) in cases.items():
        model, calls = function_model(responses)
        registry = tool_registry()

        outcome = run(PydanticAIMetricsAnalysisAgent(model).complete(usable_request(), registry))

        assert registry.ledger[-1].outcome == MetricToolRejected(reason=reason)
        assert registry.ledger[-1].executed is False
        assert registry.ledger[-1].consumed_slot is (reason != "over_budget")
        assert isinstance(outcome, MetricAgentOperationalFailure)
        assert len(calls) == expected_request_count


def test_adapter_has_no_validation_retry_or_fifth_model_request() -> None:
    model, calls = function_model([lambda _: ModelResponse(parts=[TextPart("not completion")])])

    outcome = run(PydanticAIMetricsAnalysisAgent(model).complete(usable_request(), tool_registry()))

    assert isinstance(outcome, MetricAgentOperationalFailure)
    assert len(calls) == 1


def test_adapter_rejects_invalid_tool_input_before_any_batch_admission() -> None:
    model, calls = function_model(
        [
            lambda _: ModelResponse(
                parts=[
                    ToolCallPart("spike", {}),
                    ToolCallPart("oscillation", {"unexpected": True}),
                ]
            )
        ]
    )
    registry = tool_registry()

    outcome = run(PydanticAIMetricsAnalysisAgent(model).complete(usable_request(), registry))

    assert isinstance(outcome, MetricAgentOperationalFailure)
    assert len(calls) == 1
    assert registry.ledger == ()


def test_adapter_maps_model_failure_to_operational_failure() -> None:
    def failed_model(messages, info: AgentInfo) -> ModelResponse:
        raise TimeoutError("model deadline")

    outcome = run(
        PydanticAIMetricsAnalysisAgent(FunctionModel(failed_model)).complete(
            usable_request(), tool_registry()
        )
    )

    assert isinstance(outcome, MetricAgentOperationalFailure)


def test_adapter_exposes_no_tools_for_the_insufficient_projection() -> None:
    model, calls = function_model([completion])
    request = insufficient_request()

    outcome = run(PydanticAIMetricsAnalysisAgent(model).complete(request))

    assert outcome == MetricAgentCompletion()
    assert len(calls) == 1
    messages, info = calls[0]
    assert info.function_tools == []
    assert info.model_settings == {"timeout": 120, "max_tokens": 12_288}
    assert user_prompt(messages) == request.model_dump_json(by_alias=True)


def test_enabled_metric_trace_captures_one_model_invocation_without_changing_completion(
    tmp_path,
) -> None:
    """Enabled development capture persists PydanticAI messages alongside the normal outcome."""
    model, _ = function_model([completion])
    request = usable_request()
    recorder = FileAgentTraceRecorder(root=tmp_path)

    outcome = run(
        PydanticAIMetricsAnalysisAgent(model, trace_recorder=recorder).complete(
            request, tool_registry()
        )
    )

    path = next(
        (tmp_path / str(request.identity.observation_run_id)).glob("*-metric-analysis.json")
    )
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert outcome == MetricAgentCompletion()
    assert artifact["invocation"]["lens_run_id"] == str(request.identity.lens_run_id)
    assert artifact["invocation"]["terminal_state"] == "validated_completion"
    assert artifact["model_visible"]["messages"]
    assert artifact["requests"][0]["ordinal"] == 1
    assert artifact["requests"][0]["model_settings"]["parallel_tool_calls"] is False


def test_policy_rejected_metric_trace_retains_the_raw_model_response(tmp_path) -> None:
    """Trace capture precedes policy rejection, preserving the response that triggered it."""
    model, _ = function_model([lambda _: ModelResponse(parts=[ToolCallPart("drift", {})])])
    request = usable_request()

    outcome = run(
        PydanticAIMetricsAnalysisAgent(
            model, trace_recorder=FileAgentTraceRecorder(root=tmp_path)
        ).complete(request, tool_registry())
    )

    path = next(
        (tmp_path / str(request.identity.observation_run_id)).glob("*-metric-analysis.json")
    )
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(outcome, MetricAgentOperationalFailure)
    assert artifact["raw_model_responses"][0]["parts"][0]["tool_name"] == "drift"
