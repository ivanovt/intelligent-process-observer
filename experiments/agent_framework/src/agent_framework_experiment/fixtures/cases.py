"""Deterministic, framework-neutral nonzero Alert Lens fixtures."""

from __future__ import annotations

from dataclasses import dataclass

from agent_framework_experiment.domain.contracts import (
    AlertActivity,
    AlertAnalysisInput,
    AlertRecord,
    LensContext,
    ProviderImportanceDistribution,
    ReferenceOccurrenceComparison,
    StatusDistribution,
)


@dataclass(frozen=True)
class ExperimentCase:
    name: str
    input_data: AlertAnalysisInput
    expected_tool: str | None
    expected_status: str | None
    semantic_expectation: str


def _input(
    alerts: tuple[AlertRecord, ...],
    *,
    comparisons: tuple[ReferenceOccurrenceComparison, ...] = (),
) -> AlertAnalysisInput:
    return AlertAnalysisInput(
        lens_context=LensContext(
            scope_description=(
                "Accepted Alert Lens only; immutable current and reference summaries."
            ),
            current_window="2026-08-24T09:00:00Z/2026-08-24T10:00:00Z",
            reference_window="2026-08-24T08:00:00Z/2026-08-24T09:00:00Z",
        ),
        alerts=alerts,
        activity=AlertActivity(current_count=len(alerts), reference_count=max(0, len(alerts) - 1)),
        status_distribution=StatusDistribution(
            active=sum(record.status == "active" for record in alerts),
            acknowledged=sum(record.status == "acknowledged" for record in alerts),
            resolved=sum(record.status == "resolved" for record in alerts),
        ),
        provider_importance_distribution=ProviderImportanceDistribution(
            low=sum(record.provider_importance == "low" for record in alerts),
            moderate=sum(record.provider_importance == "moderate" for record in alerts),
            high=sum(record.provider_importance == "high" for record in alerts),
            critical=sum(record.provider_importance == "critical" for record in alerts),
        ),
        reference_occurrence_comparisons=comparisons,
    )


SIMPLE_EVIDENCE = ExperimentCase(
    name="simple_evidence",
    input_data=_input(
        (
            AlertRecord(
                alert_id="A-1",
                status="active",
                occurrence_count=1,
                duration_seconds=30,
                provider_importance="high",
            ),
        ),
    ),
    expected_tool=None,
    expected_status=None,
    semantic_expectation="Produce an evidence-grounded high-importance observation without a tool.",
)

RECURRENCE_CONCENTRATION = ExperimentCase(
    name="recurrence_concentration",
    input_data=_input(
        (
            AlertRecord(
                alert_id="A-REC",
                status="active",
                occurrence_count=12,
                duration_seconds=20,
                provider_importance="moderate",
            ),
            AlertRecord(
                alert_id="A-OTHER",
                status="acknowledged",
                occurrence_count=2,
                duration_seconds=25,
                provider_importance="moderate",
            ),
        ),
    ),
    expected_tool="recurrence_concentration",
    expected_status="success",
    semantic_expectation=(
        "Recognise recurrence concentrated in A-REC when the optional tool is used."
    ),
)

# Seven identical short durations and one extreme value are outliers under common
# inclusive/exclusive/linear quartile conventions; only the convention is local.
DURATION_OUTLIER = ExperimentCase(
    name="duration_outlier",
    input_data=_input(
        tuple(
            AlertRecord(
                alert_id=f"A-D{index}",
                status="active",
                occurrence_count=1,
                duration_seconds=100 if index == 8 else 10,
                provider_importance="moderate",
            )
            for index in range(1, 9)
        ),
    ),
    expected_tool="duration_outlier",
    expected_status="success",
    semantic_expectation="Recognise A-D8 as a duration outlier when the optional tool is used.",
)

INSUFFICIENT_DURATION = ExperimentCase(
    name="insufficient_duration",
    input_data=_input(
        tuple(
            AlertRecord(
                alert_id=f"A-I{index}",
                status="active",
                occurrence_count=1,
                duration_seconds=10,
                provider_importance="low",
            )
            for index in range(1, 5)
        ),
    ),
    expected_tool="duration_outlier",
    expected_status="not_applicable",
    semantic_expectation="Continue after duration analysis has insufficient data.",
)

DOMINANT_INCREASED_REFERENCE = ExperimentCase(
    name="dominant_increased_reference_pattern",
    input_data=_input(
        (
            AlertRecord(
                alert_id="A-R1",
                status="active",
                occurrence_count=6,
                duration_seconds=15,
                provider_importance="high",
            ),
            AlertRecord(
                alert_id="A-R2",
                status="active",
                occurrence_count=5,
                duration_seconds=15,
                provider_importance="moderate",
            ),
            AlertRecord(
                alert_id="A-R3",
                status="acknowledged",
                occurrence_count=2,
                duration_seconds=15,
                provider_importance="moderate",
            ),
        ),
        comparisons=(
            ReferenceOccurrenceComparison(
                alert_id="A-R1",
                direction="increased",
                current_occurrences=6,
                reference_occurrences=2,
            ),
            ReferenceOccurrenceComparison(
                alert_id="A-R2",
                direction="increased",
                current_occurrences=5,
                reference_occurrences=2,
            ),
            ReferenceOccurrenceComparison(
                alert_id="A-R3",
                direction="unchanged",
                current_occurrences=2,
                reference_occurrences=2,
            ),
        ),
    ),
    expected_tool="reference_pattern_analysis",
    expected_status="success",
    semantic_expectation=(
        "Recognise a dominant increased reference pattern when the optional tool is used."
    ),
)

MIXED_REFERENCE = ExperimentCase(
    name="mixed_reference_pattern",
    input_data=_input(
        (
            AlertRecord(
                alert_id="A-M1",
                status="active",
                occurrence_count=3,
                duration_seconds=15,
                provider_importance="moderate",
            ),
            AlertRecord(
                alert_id="A-M2",
                status="acknowledged",
                occurrence_count=3,
                duration_seconds=15,
                provider_importance="moderate",
            ),
        ),
        comparisons=(
            ReferenceOccurrenceComparison(
                alert_id="A-M1",
                direction="increased",
                current_occurrences=3,
                reference_occurrences=1,
            ),
            ReferenceOccurrenceComparison(
                alert_id="A-M2",
                direction="decreased",
                current_occurrences=3,
                reference_occurrences=5,
            ),
        ),
    ),
    expected_tool="reference_pattern_analysis",
    expected_status="success",
    semantic_expectation="Recognise a mixed reference pattern when the optional tool is used.",
)

OPTIONAL_TOOL_FAILURE = ExperimentCase(
    name="optional_tool_failure",
    input_data=RECURRENCE_CONCENTRATION.input_data,
    expected_tool="recurrence_concentration",
    expected_status="failed",
    semantic_expectation="Continue and return a valid result after an optional tool fails.",
)

BUDGET_EXHAUSTION = ExperimentCase(
    name="budget_exhaustion",
    input_data=RECURRENCE_CONCENTRATION.input_data,
    expected_tool="recurrence_concentration",
    expected_status="success",
    semantic_expectation=(
        "The tenth invocation is recorded; the eleventh is blocked before execution."
    ),
)

ALL_CASES = (
    SIMPLE_EVIDENCE,
    RECURRENCE_CONCENTRATION,
    DURATION_OUTLIER,
    INSUFFICIENT_DURATION,
    DOMINANT_INCREASED_REFERENCE,
    MIXED_REFERENCE,
    OPTIONAL_TOOL_FAILURE,
    BUDGET_EXHAUSTION,
)
