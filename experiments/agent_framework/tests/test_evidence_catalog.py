from __future__ import annotations

import asyncio
import json

from agent_framework_experiment.agents.langchain import LangChainAlertAnalysisAgent
from agent_framework_experiment.agents.pydantic_ai import PydanticAIAlertAnalysisAgent
from agent_framework_experiment.domain import (
    AgentRunResult,
    AlertAnalysisAgentOutput,
    AlertFinding,
    base_evidence_ids,
)
from agent_framework_experiment.evaluation import evaluate_live_result
from agent_framework_experiment.fixtures.cases import (
    INSUFFICIENT_DURATION,
    OPTIONAL_TOOL_FAILURE,
    RECURRENCE_CONCENTRATION,
)
from agent_framework_experiment.tools import AnalyticalToolExecutor


def _result(*references: str, available: tuple[str, ...]) -> AgentRunResult:
    return AgentRunResult(
        output=AlertAnalysisAgentOutput(
            findings=(
                AlertFinding(
                    id="af_1",
                    statement="A bounded descriptive finding.",
                    evidence_refs=references,
                ),
            ),
            overall_importance="moderate",
        ),
        tool_attempts=(),
        available_evidence_ids=available,
    )


def test_base_catalog_is_generated_from_immutable_fixture_input() -> None:
    catalog = base_evidence_ids(RECURRENCE_CONCENTRATION.input_data)

    assert "activity.current_count" in catalog
    assert "alerts.A-REC.occurrence_count" in catalog
    assert "alerts.A-REC.occurrence_count=12" not in catalog
    assert "alerts[0].occurrence_count" not in catalog


def test_allowed_unknown_and_value_appended_base_references_are_distinguished() -> None:
    available = base_evidence_ids(RECURRENCE_CONCENTRATION.input_data)

    allowed = evaluate_live_result(
        RECURRENCE_CONCENTRATION,
        _result("alerts.A-REC.occurrence_count", available=available),
    )
    unknown = evaluate_live_result(
        RECURRENCE_CONCENTRATION,
        _result("alerts.A-UNKNOWN.occurrence_count", available=available),
    )
    value_appended = evaluate_live_result(
        RECURRENCE_CONCENTRATION,
        _result("alerts.A-REC.occurrence_count=12", available=available),
    )

    assert allowed["hard_correctness"]["evidence_refs_valid"] is True
    assert unknown["hard_correctness"]["evidence_refs_valid"] is False
    assert value_appended["hard_correctness"]["evidence_refs_valid"] is False


def test_successful_tool_exposes_canonical_tool_evidence_only_after_execution() -> None:
    async def exercise() -> None:
        executor = AnalyticalToolExecutor(RECURRENCE_CONCENTRATION.input_data)
        before = executor.available_evidence_ids
        assert "tool.recurrence_concentration.dominant_share" not in before
        unavailable = evaluate_live_result(
            RECURRENCE_CONCENTRATION,
            _result("tool.recurrence_concentration.dominant_share", available=before),
        )
        assert unavailable["hard_correctness"]["evidence_refs_valid"] is False

        result = await executor.invoke("recurrence_concentration")

        assert result.status == "success"
        assert (
            "tool.recurrence_concentration.dominant_share" in result.data["available_evidence_ids"]
        )
        assert "tool.recurrence_concentration.dominant_share" in executor.available_evidence_ids
        evaluated = evaluate_live_result(
            RECURRENCE_CONCENTRATION,
            _result(
                "tool.recurrence_concentration.dominant_share",
                available=executor.available_evidence_ids,
            ),
        )
        assert evaluated["hard_correctness"]["evidence_refs_valid"] is True

    asyncio.run(exercise())


def test_failed_timeout_and_not_applicable_tools_do_not_expose_successful_evidence() -> None:
    async def controlled_timeout(_input):
        await asyncio.Event().wait()

    def controlled_failure(_input):
        raise RuntimeError("controlled fixture failure")

    async def exercise() -> None:
        failed = AnalyticalToolExecutor(
            OPTIONAL_TOOL_FAILURE.input_data,
            handlers={"recurrence_concentration": controlled_failure},
        )
        assert (await failed.invoke("recurrence_concentration")).status == "failed"
        assert "tool.recurrence_concentration.dominant_share" not in failed.available_evidence_ids
        assert (
            evaluate_live_result(
                OPTIONAL_TOOL_FAILURE,
                _result(
                    "tool.recurrence_concentration.dominant_share",
                    available=failed.available_evidence_ids,
                ),
            )["hard_correctness"]["evidence_refs_valid"]
            is False
        )

        timed_out = AnalyticalToolExecutor(
            OPTIONAL_TOOL_FAILURE.input_data,
            timeout_seconds=0.001,
            handlers={"recurrence_concentration": controlled_timeout},
        )
        assert (await timed_out.invoke("recurrence_concentration")).status == "timeout"
        assert (
            "tool.recurrence_concentration.dominant_share" not in timed_out.available_evidence_ids
        )
        assert (
            evaluate_live_result(
                OPTIONAL_TOOL_FAILURE,
                _result(
                    "tool.recurrence_concentration.dominant_share",
                    available=timed_out.available_evidence_ids,
                ),
            )["hard_correctness"]["evidence_refs_valid"]
            is False
        )

        not_applicable = AnalyticalToolExecutor(INSUFFICIENT_DURATION.input_data)
        assert (await not_applicable.invoke("duration_outlier")).status == "not_applicable"
        assert "tool.duration_outlier.upper_bound" not in not_applicable.available_evidence_ids
        assert (
            evaluate_live_result(
                INSUFFICIENT_DURATION,
                _result(
                    "tool.duration_outlier.upper_bound",
                    available=not_applicable.available_evidence_ids,
                ),
            )["hard_correctness"]["evidence_refs_valid"]
            is False
        )

    asyncio.run(exercise())


def test_both_adapters_receive_the_same_canonical_input_catalog() -> None:
    input_data = RECURRENCE_CONCENTRATION.input_data
    expected_catalog = base_evidence_ids(input_data)
    pydantic_payload = PydanticAIAlertAnalysisAgent.render_user_input(input_data)
    langchain_payload = LangChainAlertAnalysisAgent.render_user_input(input_data)

    assert pydantic_payload == langchain_payload
    payload_json = pydantic_payload.removeprefix(
        "Immutable Alert Lens input and experiment-local evidence catalog (JSON):\n"
    )
    assert tuple(json.loads(payload_json)["available_evidence_ids"]) == expected_catalog
    assert AnalyticalToolExecutor(input_data).available_evidence_ids == expected_catalog
