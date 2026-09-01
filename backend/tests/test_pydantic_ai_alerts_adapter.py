from __future__ import annotations

import asyncio
from datetime import UTC, datetime

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
from app.infrastructure.agents.pydantic_ai_alerts import PydanticAIAlertAnalysisAgent

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


def test_forbidden_requests_are_rejected_and_budget_rejection_then_completes() -> None:
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
        "over_budget": [
            *[
                lambda _: ModelResponse(
                    parts=[ToolCallPart("recurrence_concentration_analysis", {})]
                )
                for _ in range(11)
            ],
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
        assert len(calls) == (12 if reason == "over_budget" else 2)


def test_forbidden_request_model_counts_have_no_corrective_retry() -> None:
    test_forbidden_requests_are_rejected_and_budget_rejection_then_completes()


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
