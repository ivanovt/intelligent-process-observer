"""Deterministic optional Alert analytical tools, independent of agent frameworks."""

from __future__ import annotations

from collections import Counter
from statistics import quantiles

from agent_framework_experiment.domain.contracts import AlertAnalysisInput, ToolExecutionResult


def recurrence_concentration(input_data: AlertAnalysisInput) -> ToolExecutionResult:
    occurrences = {record.alert_id: record.occurrence_count for record in input_data.alerts}
    total = sum(occurrences.values())
    if total == 0:
        return ToolExecutionResult(status="not_applicable", data={"reason": "no_occurrences"})
    dominant_id, dominant_count = max(occurrences.items(), key=lambda item: item[1])
    return ToolExecutionResult(
        status="success",
        data={
            "dominant_alert_id": dominant_id,
            "dominant_occurrence_count": dominant_count,
            "total_occurrence_count": total,
            "dominant_share": dominant_count / total,
            "evidence_ref": f"alerts.{dominant_id}.occurrence_count",
        },
    )


def duration_outlier(input_data: AlertAnalysisInput) -> ToolExecutionResult:
    durations = [
        record.duration_seconds
        for record in input_data.alerts
        if record.duration_seconds is not None
    ]
    if len(durations) < 8:
        return ToolExecutionResult(
            status="not_applicable",
            data={"reason": "insufficient_valid_durations", "valid_duration_count": len(durations)},
        )

    # Experiment-local convention only: statistics.quantiles(..., method="inclusive").
    q1, _, q3 = quantiles(durations, n=4, method="inclusive")
    iqr = q3 - q1
    upper_bound = q3 + 1.5 * iqr
    outliers = [
        {"alert_id": record.alert_id, "duration_seconds": record.duration_seconds}
        for record in input_data.alerts
        if record.duration_seconds is not None and record.duration_seconds > upper_bound
    ]
    return ToolExecutionResult(
        status="success",
        data={
            "quartile_method": "python_statistics_inclusive",
            "valid_duration_count": len(durations),
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "upper_bound": upper_bound,
            "outliers": outliers,
        },
    )


def reference_pattern_analysis(input_data: AlertAnalysisInput) -> ToolExecutionResult:
    comparisons = input_data.reference_occurrence_comparisons
    if len(comparisons) < 2:
        return ToolExecutionResult(
            status="not_applicable",
            data={
                "reason": "insufficient_reference_comparisons",
                "comparison_count": len(comparisons),
            },
        )
    directions = Counter(comparison.direction for comparison in comparisons)
    most_common = directions.most_common()
    pattern = (
        "mixed"
        if len(most_common) > 1 and most_common[0][1] == most_common[1][1]
        else most_common[0][0]
    )
    return ToolExecutionResult(
        status="success",
        data={
            "pattern": pattern,
            "direction_counts": dict(directions),
            "comparison_count": len(comparisons),
            "evidence_refs": tuple(
                f"reference_occurrence_comparisons.{comparison.alert_id}"
                for comparison in comparisons
            ),
        },
    )
