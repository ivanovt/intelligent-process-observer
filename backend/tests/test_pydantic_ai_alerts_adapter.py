from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.alerts.contracts import (
    AlertAgentRequest,
    AlertMandatoryEvidence,
    AlertStatus,
    CanonicalAlertRecord,
)
from app.alerts.tools import AlertOptionalToolRegistry
from app.infrastructure.agents.pydantic_ai_alerts import (
    AlertAgentPolicyViolation,
    PydanticAIAlertAnalysisAgent,
)
from app.infrastructure.agents.tracing import (
    AgentTraceContext,
    FileAgentTraceRecorder,
    activate_trace_context,
)

START = datetime(2026, 8, 30, tzinfo=UTC)


def run(coroutine):
    return asyncio.run(coroutine)


def request() -> AlertAgentRequest:
    record = CanonicalAlertRecord(
        id="alert-1",
        title="High temperature",
        started_at=START,
        duration_seconds=60.0,
        status=AlertStatus(normalized="active", source="open"),
    )
    return AlertAgentRequest(
        lens_name="Temperature alerts",
        current_records=(record,),
        mandatory_evidence=AlertMandatoryEvidence.model_validate(
            {
                "alert_activity": {"record_count": 1, "occurrence_count": 1},
                "status_distribution": {"active": 1, "resolved": 0, "unknown": 0},
                "duration_statistics": {
                    "min_seconds": 60.0,
                    "max_seconds": 60.0,
                    "average_seconds": 60.0,
                },
            }
        ),
    )


def registry() -> AlertOptionalToolRegistry:
    value = request()
    return AlertOptionalToolRegistry(value.current_records, value.mandatory_evidence)


def completion(info: AgentInfo) -> ModelResponse:
    return ModelResponse(
        parts=[
            ToolCallPart(
                info.output_tools[0].name,
                {"findings": (), "overall_importance": "low"},
            )
        ]
    )


def model(responses):
    calls = []

    def scripted(messages, info: AgentInfo) -> ModelResponse:
        calls.append((messages, info))
        return responses[len(calls) - 1](info)

    return FunctionModel(scripted), calls


def test_valid_zero_call_completion_is_injected_and_bounded() -> None:
    injected, calls = model([completion])
    outcome = run(PydanticAIAlertAnalysisAgent(injected).complete(request(), registry()))
    assert outcome.overall_importance == "low"
    assert outcome.findings == ()
    assert len(calls) == 1
    messages, info = calls[0]
    assert [tool.name for tool in info.function_tools] == [
        "recurrence_concentration_analysis",
        "duration_outlier_analysis",
        "reference_pattern_analysis",
    ]
    prompt = next(
        part.content
        for message in messages
        for part in message.parts
        if part.part_kind == "user-prompt"
    )
    assert prompt == request().model_dump_json(by_alias=True)
    assert "query" not in prompt


def test_repeated_calls_through_tenth_use_domain_executor() -> None:
    calls_to_tool = [
        lambda _: ModelResponse(parts=[ToolCallPart("recurrence_concentration_analysis", {})])
        for _ in range(10)
    ]
    injected, calls = model([*calls_to_tool, completion])
    tools = registry()
    outcome = run(PydanticAIAlertAnalysisAgent(injected).complete(request(), tools))
    assert outcome.overall_importance == "low"
    assert [(item.ordinal, item.requested_name, item.executed) for item in tools.ledger] == [
        (ordinal, "recurrence_concentration_analysis", True) for ordinal in range(1, 11)
    ]
    assert len(calls) == 11


def test_forbidden_requests_before_the_final_request_are_routed_to_the_registry() -> None:
    cases = {
        "unregistered": [
            lambda _: ModelResponse(parts=[ToolCallPart("scope_expansion", {})]),
            completion,
        ],
        "invalid_arguments": [
            lambda _: ModelResponse(
                parts=[ToolCallPart("recurrence_concentration_analysis", {"period": "1d"})]
            ),
            completion,
        ],
    }
    for reason, responses in cases.items():
        injected, calls = model(responses)
        tools = registry()
        outcome = run(PydanticAIAlertAnalysisAgent(injected).complete(request(), tools))
        assert outcome.overall_importance == "low"
        assert tools.ledger[-1].outcome.reason == reason
        assert tools.ledger[-1].executed is False
        assert len(calls) == 2


def test_forbidden_request_model_counts_have_no_corrective_retry() -> None:
    injected, calls = model(
        [
            *[
                lambda _: ModelResponse(
                    parts=[ToolCallPart("recurrence_concentration_analysis", {})]
                )
                for _ in range(10)
            ],
            lambda _: ModelResponse(parts=[ToolCallPart("recurrence_concentration_analysis", {})]),
        ]
    )
    tools = registry()

    with pytest.raises(AlertAgentPolicyViolation):
        run(PydanticAIAlertAnalysisAgent(injected).complete(request(), tools))

    assert len(calls) == 11
    assert len(tools.ledger) == 10


def test_multi_call_response_stops_at_remaining_capacity_without_excess_ledger_entry() -> None:
    injected, calls = model(
        [
            *[
                lambda _: ModelResponse(
                    parts=[ToolCallPart("recurrence_concentration_analysis", {})]
                )
                for _ in range(9)
            ],
            lambda _: ModelResponse(
                parts=[
                    ToolCallPart("recurrence_concentration_analysis", {}),
                    ToolCallPart("duration_outlier_analysis", {}),
                ]
            ),
        ]
    )
    tools = registry()

    with pytest.raises(AlertAgentPolicyViolation):
        run(PydanticAIAlertAnalysisAgent(injected).complete(request(), tools))

    assert len(calls) == 10
    assert [(item.ordinal, item.requested_name) for item in tools.ledger] == [
        (ordinal, "recurrence_concentration_analysis") for ordinal in range(1, 11)
    ]


def test_invalid_completion_failure_counts_have_no_corrective_retry() -> None:
    def invalid(_: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[ToolCallPart("final_result", {"findings": (), "overall_importance": "none"})]
        )

    def model_error(_: AgentInfo) -> ModelResponse:
        raise RuntimeError("model failure")

    def timeout(_: AgentInfo) -> ModelResponse:
        raise TimeoutError("model deadline")

    for terminal_response, error_type in (
        (invalid, UnexpectedModelBehavior),
        (model_error, RuntimeError),
        (timeout, TimeoutError),
    ):
        injected, calls = model([terminal_response])
        with pytest.raises(error_type):
            run(PydanticAIAlertAnalysisAgent(injected).complete(request(), registry()))
        assert len(calls) == 1


def test_empty_finding_evidence_references_are_rejected_by_adapter() -> None:
    def invalid(_: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "final_result",
                    {
                        "findings": [
                            {
                                "id": "ungrounded",
                                "statement": "missing support",
                                "evidence_refs": [],
                            }
                        ],
                        "overall_importance": "high",
                    },
                )
            ]
        )

    injected, calls = model([invalid])
    with pytest.raises(UnexpectedModelBehavior):
        run(PydanticAIAlertAnalysisAgent(injected).complete(request(), registry()))
    assert len(calls) == 1


def test_invalid_completion_error_and_timeout_map_exactly() -> None:
    invalid, invalid_calls = model(
        [
            lambda _: ModelResponse(
                parts=[ToolCallPart("final_result", {"findings": (), "overall_importance": "none"})]
            )
        ]
    )
    with pytest.raises(UnexpectedModelBehavior):
        run(PydanticAIAlertAnalysisAgent(invalid).complete(request(), registry()))
    assert len(invalid_calls) == 1

    def timeout(_: object, __: AgentInfo) -> ModelResponse:
        raise TimeoutError("model deadline")

    with pytest.raises(TimeoutError):
        run(PydanticAIAlertAnalysisAgent(FunctionModel(timeout)).complete(request(), registry()))


def test_optional_timeout_continues_to_valid_completion() -> None:
    def timeout_evaluator():
        raise TimeoutError("tool deadline")

    value = request()
    tools = AlertOptionalToolRegistry(
        value.current_records,
        value.mandatory_evidence,
        evaluators={
            "recurrence_concentration_analysis": timeout_evaluator,
            "duration_outlier_analysis": timeout_evaluator,
            "reference_pattern_analysis": timeout_evaluator,
        },
    )
    injected, calls = model(
        [
            lambda _: ModelResponse(parts=[ToolCallPart("recurrence_concentration_analysis", {})]),
            completion,
        ]
    )
    outcome = run(PydanticAIAlertAnalysisAgent(injected).complete(value, tools))
    assert outcome.overall_importance == "low"
    assert tools.ledger[0].outcome.outcome == "timeout"
    assert len(calls) == 2


def test_instructions_preserve_lens_local_descriptive_boundary() -> None:
    injected, calls = model([completion])
    run(PydanticAIAlertAnalysisAgent(injected).complete(request(), registry()))
    prompt = " ".join(
        part.content
        for message in calls[0][0]
        for part in message.parts
        if part.part_kind == "system-prompt"
    ).lower()
    for required in ("deduplicated", "lens-local", "descriptive"):
        assert required in prompt
    for forbidden in (
        "causes",
        "recommendations",
        "semantically cluster",
        "cross-lens",
        "rag",
        "external knowledge",
        "missing data",
        "expand scope",
    ):
        assert forbidden in prompt


def test_enabled_alert_trace_uses_out_of_band_correlation_without_changing_request_shape(
    tmp_path,
) -> None:
    """Alert capture uses the pipeline context rather than serializing trace fields into input."""
    injected, _ = model([completion])
    recorder = FileAgentTraceRecorder(root=tmp_path)
    trace_context = AgentTraceContext(
        observation_run_id=uuid4(),
        lens_run_id=uuid4(),
        lens_id="temperature-alerts",
        agent_role="alert",
        phase="analysis",
        model="test/model",
    )
    value = request()

    with activate_trace_context(trace_context):
        outcome = run(
            PydanticAIAlertAnalysisAgent(injected, trace_recorder=recorder).complete(
                value, registry()
            )
        )

    path = next((tmp_path / str(trace_context.observation_run_id)).glob("*-alert-analysis.json"))
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert outcome.overall_importance == "low"
    assert "trace_identity" not in value.model_dump()
    assert artifact["invocation"]["lens_run_id"] == str(trace_context.lens_run_id)


def test_policy_transformed_alert_response_remains_raw_in_the_trace(tmp_path) -> None:
    """The trace retains the pre-transformation tool name that the policy rejected."""
    injected, _ = model([lambda _: ModelResponse(parts=[ToolCallPart("scope_expansion", {})])])
    recorder = FileAgentTraceRecorder(root=tmp_path)
    trace_context = AgentTraceContext(
        observation_run_id=uuid4(),
        lens_run_id=uuid4(),
        lens_id="temperature-alerts",
        agent_role="alert",
        phase="analysis",
        model="test/model",
    )

    with activate_trace_context(trace_context), pytest.raises(IndexError):
        run(
            PydanticAIAlertAnalysisAgent(injected, trace_recorder=recorder).complete(
                request(), registry()
            )
        )

    path = next((tmp_path / str(trace_context.observation_run_id)).glob("*-alert-analysis.json"))
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert artifact["raw_model_responses"][0]["parts"][0]["tool_name"] == "scope_expansion"
