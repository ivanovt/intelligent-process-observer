from __future__ import annotations

import asyncio

import pytest

from agent_framework_experiment.domain import ToolBudgetExhausted, ToolExecutionResult
from agent_framework_experiment.fixtures.cases import (
    BUDGET_EXHAUSTION,
    DOMINANT_INCREASED_REFERENCE,
    DURATION_OUTLIER,
    INSUFFICIENT_DURATION,
    MIXED_REFERENCE,
    RECURRENCE_CONCENTRATION,
)
from agent_framework_experiment.tools import (
    AnalyticalToolExecutor,
    duration_outlier,
    recurrence_concentration,
    reference_pattern_analysis,
)


def test_recurrence_concentration_is_deterministic() -> None:
    result = recurrence_concentration(RECURRENCE_CONCENTRATION.input_data)

    assert result.status == "success"
    assert result.data["dominant_alert_id"] == "A-REC"
    assert result.data["dominant_share"] == pytest.approx(12 / 14)


def test_duration_outlier_is_robust_and_uses_experiment_local_convention() -> None:
    result = duration_outlier(DURATION_OUTLIER.input_data)

    assert result.status == "success"
    assert result.data["quartile_method"] == "python_statistics_inclusive"
    assert result.data["outliers"] == [{"alert_id": "A-D8", "duration_seconds": 100.0}]


def test_insufficient_duration_is_a_normal_not_applicable_result() -> None:
    result = duration_outlier(INSUFFICIENT_DURATION.input_data)

    assert result.status == "not_applicable"
    assert result.data["valid_duration_count"] == 4


def test_reference_patterns_cover_dominant_and_mixed_cases() -> None:
    dominant = reference_pattern_analysis(DOMINANT_INCREASED_REFERENCE.input_data)
    mixed = reference_pattern_analysis(MIXED_REFERENCE.input_data)

    assert dominant.data["pattern"] == "increased"
    assert mixed.data["pattern"] == "mixed"


def test_failure_and_timeout_are_traced_and_do_not_stop_later_tools() -> None:
    async def controlled_timeout(_input):
        await asyncio.Event().wait()

    def controlled_failure(_input):
        raise RuntimeError("fixture failure")

    async def exercise() -> None:
        executor = AnalyticalToolExecutor(
            RECURRENCE_CONCENTRATION.input_data,
            timeout_seconds=0.001,
            handlers={
                "recurrence_concentration": controlled_failure,
                "duration_outlier": controlled_timeout,
            },
        )
        failed = await executor.invoke("recurrence_concentration")
        timed_out = await executor.invoke("duration_outlier")
        succeeded = await executor.invoke("reference_pattern_analysis")

        assert failed == ToolExecutionResult(status="failed", data={"reason": "tool_failed"})
        assert timed_out == ToolExecutionResult(status="timeout", data={"reason": "tool_timeout"})
        assert succeeded.status == "not_applicable"
        assert [trace.status for trace in executor.traces] == [
            "failed",
            "timeout",
            "not_applicable",
        ]
        assert [trace.invocation_order for trace in executor.traces] == [1, 2, 3]
        assert all(trace.latency_ms >= 0 for trace in executor.traces)

    asyncio.run(exercise())


def test_domain_budget_allows_tenth_and_blocks_eleventh_before_execution() -> None:
    async def exercise() -> None:
        executor = AnalyticalToolExecutor(BUDGET_EXHAUSTION.input_data)
        for _ in range(10):
            assert (await executor.invoke("recurrence_concentration")).status == "success"
        assert len(executor.traces) == 10
        assert executor.traces[-1].invocation_order == 10
        with pytest.raises(ToolBudgetExhausted):
            await executor.invoke("recurrence_concentration")
        blocked = await executor.invoke_from_adapter("recurrence_concentration")
        assert blocked == {"status": "blocked", "reason": "analytical_tool_budget_exhausted"}
        assert len(executor.traces) == 10
        assert executor.blocked_tool_calls == 1

    asyncio.run(exercise())
