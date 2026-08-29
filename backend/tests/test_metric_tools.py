from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.metrics.contracts import MetricEvidence, MetricSample, PreparedGoodSeries
from app.metrics.tools import (
    MetricToolRegistry,
    analyze_oscillation,
    analyze_spike,
    analyze_stuck_signal,
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
    with pytest.raises(KeyError):
        asyncio.run(registry.execute("drift"))
    assert registry.ledger == ()


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


def test_stuck_signal_uses_exact_values_threshold_and_earliest_longest_run() -> None:
    present = analyze_stuck_signal(prepared((2.0, 2.0, 2.0, 2.0, 3.0)))
    absent = analyze_stuck_signal(prepared((5.0, 5.0, 1.0, 1.0, 2.0, 2.0)))
    assert present.state == "present"
    assert present.evidence.longest_run_share == 0.80
    assert absent.state == "absent"
    assert absent.evidence.repeated_value == 5.0
    assert analyze_stuck_signal(prepared((1.0, 1.0, 1.0, 1.0))).outcome == "not_applicable"
