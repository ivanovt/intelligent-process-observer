from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime, timedelta

import pytest

from app.metrics.contracts import MetricEvidence, MetricSample, PreparedGoodSeries
from app.metrics.tools import (
    MetricToolRegistry,
    analyze_oscillation,
    analyze_spike,
    analyze_stuck_signal,
    project_successful_optional_tools,
)

START = datetime(2026, 8, 28, tzinfo=UTC)


def prepared(
    values: tuple[float, ...], *, residuals: tuple[float, ...] | None = None
) -> PreparedGoodSeries:
    return PreparedGoodSeries(
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
        residuals=residuals if residuals is not None else (0.0,) * len(values),
    )


def test_registry_is_exactly_the_three_approved_tools_and_binds_one_dataset() -> None:
    series = prepared((1.0, 2.0, 3.0, 4.0, 5.0))
    registry = MetricToolRegistry("opaque-run-dataset", series)

    assert tuple(item.name for item in registry.descriptors) == (
        "spike",
        "oscillation",
        "stuck_signal",
    )
    assert tuple(item.capability for item in registry.descriptors) == (
        "isolated_extreme_detection",
        "detrended_residual_alternation",
        "exact_repeated_value_run_detection",
    )
    assert tuple(item.minimum_samples for item in registry.descriptors) == (5, 8, 5)
    rejected = asyncio.run(registry.execute("drift"))
    assert rejected.outcome == "rejected"
    assert rejected.reason == "unregistered"
    assert registry.ledger[0].model_dump() == {
        "ordinal": 1,
        "requested_name": "drift",
        "outcome": {"outcome": "rejected", "reason": "unregistered"},
        "executed": False,
        "consumed_slot": True,
    }


def test_request_policy_records_duplicate_unregistered_and_over_budget() -> None:
    registry = MetricToolRegistry("opaque-run-dataset", prepared((1.0, 2.0, 3.0, 4.0, 5.0)))

    async def scenario() -> None:
        await registry.execute("spike")
        duplicate = await registry.execute("spike")
        unregistered = await registry.execute("drift")
        over_budget = await registry.execute("stuck_signal")

        assert duplicate.reason == "duplicate"
        assert unregistered.reason == "unregistered"
        assert over_budget.reason == "over_budget"

    asyncio.run(scenario())

    assert [
        (attempt.ordinal, attempt.requested_name, attempt.executed, attempt.consumed_slot)
        for attempt in registry.ledger
    ] == [
        (1, "spike", True, True),
        (2, "spike", False, True),
        (3, "drift", False, True),
        (4, "stuck_signal", False, False),
    ]
    assert [getattr(attempt.outcome, "outcome", "success") for attempt in registry.ledger] == [
        "success",
        "rejected",
        "rejected",
        "rejected",
    ]
    assert [getattr(attempt.outcome, "reason", None) for attempt in registry.ledger] == [
        None,
        "duplicate",
        "unregistered",
        "over_budget",
    ]
    assert registry.protocol_failure is not None
    projections = project_successful_optional_tools(registry.ledger)
    assert projections.spike is not None
    assert projections.oscillation is None
    assert projections.stuck_signal is None


def test_request_policy_rejects_batched_parallel_execution_with_synchronous_evaluators() -> None:
    series = prepared((1.0, 2.0, 3.0, 4.0, 5.0))
    registry = MetricToolRegistry("opaque-run-dataset", series)

    async def scenario() -> None:
        first, parallel = await registry.execute_batch(("spike", "oscillation"))

        assert first.model_dump()["name"] == "spike"
        assert parallel.outcome == "rejected"
        assert parallel.reason == "parallel"

    asyncio.run(scenario())

    assert [
        (attempt.ordinal, attempt.requested_name, attempt.executed, attempt.consumed_slot)
        for attempt in registry.ledger
    ] == [(1, "spike", True, True), (2, "oscillation", False, True)]


def test_spike_covers_modified_z_and_every_zero_mad_branch() -> None:
    modified = analyze_spike(prepared((1.0, 2.0, 2.0, 3.0, 100.0)))
    assert modified.state == "present"
    assert modified.evidence.method == "modified_z"
    assert modified.evidence.detected_sample_count == 1

    absent = analyze_spike(prepared((7.0, 7.0, 7.0, 7.0, 7.0)))
    sparse = analyze_spike(prepared((7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 8.0)))
    excessive_values = (7.0,) * 9 + (8.0, 9.0)
    excessive = analyze_spike(prepared(excessive_values))
    assert (absent.state, sparse.state, excessive.state) == ("absent", "present", "unknown")
    assert absent.evidence.method == sparse.evidence.method == excessive.evidence.method
    assert absent.evidence.detected_sample_count == 0
    assert sparse.evidence.detected_sample_count == 1
    assert excessive.evidence.detected_sample_count == 0
    assert "max_abs_modified_z" not in excessive.evidence.model_dump()
    assert analyze_spike(prepared((1.0, 2.0, 3.0, 4.0))).outcome == "not_applicable"


@pytest.mark.parametrize(
    ("score", "state", "detected_sample_count"),
    (
        (math.nextafter(3.5, -math.inf), "absent", 0),
        (3.5, "absent", 0),
        (math.nextafter(3.5, math.inf), "present", 1),
    ),
)
def test_spike_modified_z_uses_a_strict_3_5_threshold(
    score: float, state: str, detected_sample_count: int
) -> None:
    outcome = analyze_spike(prepared((-1.0, -1.0, 0.0, 1.0, score / 0.6745)))

    assert outcome.state == state
    assert outcome.evidence.detected_sample_count == detected_sample_count


def test_oscillation_covers_present_absent_unknown_and_minimum_samples() -> None:
    present = analyze_oscillation(
        prepared(
            (0.0, 10.0, 0.0, 10.0, 0.0, 10.0, 0.0, 10.0),
            residuals=(-1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0),
        )
    )
    unknown = analyze_oscillation(
        prepared(
            (0.0, 10.0, 0.0, 10.0, 0.0, 10.0, 0.0, 10.0),
            residuals=(-1.0, 1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        )
    )
    absent = analyze_oscillation(prepared((1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)))
    assert (present.state, unknown.state, absent.state) == ("present", "unknown", "absent")
    assert present.evidence.sign_change_count == 7
    assert present.evidence.sign_change_ratio == 1.0
    assert unknown.evidence.sign_change_ratio == 1.0
    assert absent.evidence.significant_residual_count == 0
    assert analyze_oscillation(prepared((1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0))).outcome == (
        "not_applicable"
    )


def _residuals_with_sign_changes(
    count: int, sign_change_count: int, magnitude: float
) -> tuple[float, ...]:
    alternating = tuple(
        magnitude if index % 2 == 0 else -magnitude for index in range(sign_change_count + 1)
    )
    return alternating + (alternating[-1],) * (count - len(alternating))


@pytest.mark.parametrize(
    ("residuals", "state", "significant_count", "sign_change_count"),
    (
        ((5.0, -5.0) * 4, "unknown", 0, 0),
        ((math.nextafter(5.0, math.inf), -math.nextafter(5.0, math.inf)) * 4, "present", 8, 7),
        (_residuals_with_sign_changes(101, 59, 10.0), "absent", 101, 59),
        (_residuals_with_sign_changes(101, 60, 10.0), "present", 101, 60),
    ),
    ids=("deadband-equality", "deadband-immediately-above", "ratio-below", "ratio-equality"),
)
def test_oscillation_uses_strict_deadband_and_inclusive_ratio_boundary(
    residuals: tuple[float, ...],
    state: str,
    significant_count: int,
    sign_change_count: int,
) -> None:
    values = tuple(0.0 if index % 2 == 0 else 100.0 for index in range(len(residuals)))
    outcome = analyze_oscillation(prepared(values, residuals=residuals))

    assert outcome.state == state
    assert outcome.evidence.deadband == 5.0
    assert outcome.evidence.significant_residual_count == significant_count
    assert outcome.evidence.sign_change_count == sign_change_count
    assert outcome.evidence.sign_change_ratio == sign_change_count / max(significant_count - 1, 1)


def test_stuck_signal_uses_exact_values_threshold_and_earliest_longest_run() -> None:
    present = analyze_stuck_signal(prepared((2.0, 2.0, 2.0, 2.0, 3.0)))
    absent = analyze_stuck_signal(prepared((5.0, 5.0, 1.0, 1.0, 2.0, 2.0)))
    assert present.state == "present"
    assert present.evidence.longest_run_share == 0.80
    assert absent.state == "absent"
    assert absent.evidence.repeated_value == 5.0
    assert analyze_stuck_signal(prepared((1.0, 1.0, 1.0, 1.0))).outcome == "not_applicable"
