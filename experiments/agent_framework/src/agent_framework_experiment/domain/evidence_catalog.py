"""Experiment-local evidence IDs; this is not a production result-contract grammar."""

from __future__ import annotations

from agent_framework_experiment.domain.contracts import AlertAnalysisInput, ToolExecutionResult


def base_evidence_ids(input_data: AlertAnalysisInput) -> tuple[str, ...]:
    """Generate every input-backed ID available to one immutable Alert Lens input."""

    ids: set[str] = set()
    ids.update(f"activity.{name}" for name in type(input_data.activity).model_fields)
    ids.update(
        f"status_distribution.{name}" for name in type(input_data.status_distribution).model_fields
    )
    ids.update(
        f"provider_importance_distribution.{name}"
        for name in type(input_data.provider_importance_distribution).model_fields
    )
    for alert in input_data.alerts:
        ids.update(f"alerts.{alert.alert_id}.{name}" for name in type(alert).model_fields)
    for comparison in input_data.reference_occurrence_comparisons:
        ids.update(
            f"reference_occurrence_comparisons.{comparison.alert_id}.{name}"
            for name in type(comparison).model_fields
        )
    return tuple(sorted(ids))


def successful_tool_evidence_ids(tool_name: str, result: ToolExecutionResult) -> tuple[str, ...]:
    """Expose result-backed IDs only when a shared optional tool succeeds."""

    if result.status != "success":
        return ()
    available_by_tool = {
        "recurrence_concentration": (
            "dominant_alert_id",
            "dominant_occurrence_count",
            "total_occurrence_count",
            "dominant_share",
        ),
        "duration_outlier": (
            "quartile_method",
            "valid_duration_count",
            "q1",
            "q3",
            "iqr",
            "upper_bound",
            "outlier_alert_ids",
        ),
        "reference_pattern_analysis": (
            "pattern",
            "direction_counts",
            "comparison_count",
        ),
    }
    try:
        names = available_by_tool[tool_name]
    except KeyError as error:
        raise ValueError(f"unknown analytical tool: {tool_name}") from error
    return tuple(f"tool.{tool_name}.{name}" for name in names)


def attach_successful_tool_evidence(
    tool_name: str, result: ToolExecutionResult
) -> ToolExecutionResult:
    """Add catalog IDs to the tool observation without changing analytical logic."""

    evidence_ids = successful_tool_evidence_ids(tool_name, result)
    if not evidence_ids:
        return result
    data = dict(result.data or {})
    if tool_name == "duration_outlier":
        data["outlier_alert_ids"] = [item["alert_id"] for item in data.get("outliers", [])]
    data["available_evidence_ids"] = evidence_ids
    return ToolExecutionResult(status=result.status, data=data)
