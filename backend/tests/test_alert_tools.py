"""Focused proofs for the bounded optional Alert tool registry."""

import asyncio
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.alerts.contracts import (
    AlertActivity,
    AlertMandatoryEvidence,
    AlertOccurrenceComparison,
    AlertOptionalToolExecution,
    AlertOptionalToolSuccess,
    AlertReferenceComparison,
    AlertStatus,
    AlertStatusDistribution,
    AlertUnsuccessfulToolCall,
    CanonicalAlertRecord,
)
from app.alerts.tools import AlertOptionalToolRegistry


def _records(
    durations: tuple[float, ...], occurrences: tuple[int | None, ...] = ()
) -> tuple[CanonicalAlertRecord, ...]:
    return tuple(
        CanonicalAlertRecord(
            id=f"id-{index}",
            title=f"Alert {index}",
            started_at=datetime(2026, 9, 1, tzinfo=UTC),
            duration_seconds=duration,
            status=AlertStatus(normalized="active", source="active"),
            occurrence_count=occurrences[index] if occurrences else 1,
        )
        for index, duration in enumerate(durations)
    )


def _evidence(
    records: tuple[CanonicalAlertRecord, ...],
    comparisons: tuple[AlertReferenceComparison, ...] = (),
) -> AlertMandatoryEvidence:
    return AlertMandatoryEvidence(
        alert_activity=AlertActivity(
            record_count=len(records),
            occurrence_count=sum(
                record.occurrence_count if record.occurrence_count is not None else 1
                for record in records
            ),
        ),
        status_distribution=AlertStatusDistribution(active=len(records), resolved=0, unknown=0),
        comparisons=comparisons,
    )


def test_optional_registry_enforces_scope_repeats_and_ten_attempt_budget() -> None:
    async def scenario() -> None:
        records = _records((1.0,), (2,))
        registry = AlertOptionalToolRegistry(records, _evidence(records))
        names = ["recurrence_concentration_analysis"] * 10
        outcomes = [await registry.execute(name, {}) for name in names]
        assert all(outcome.outcome == "success" for outcome in outcomes)
        eleventh = await registry.execute("duration_outlier_analysis", {})
        assert eleventh.outcome == "rejected" and eleventh.reason == "over_budget"
        assert [attempt.ordinal for attempt in registry.ledger] == list(range(1, 12))
        assert all(attempt.executed for attempt in registry.ledger[:-1])
        assert not registry.ledger[-1].executed
        assert records == _records((1.0,), (2,))

        rejected = AlertOptionalToolRegistry(records, _evidence(records))
        unknown = await rejected.execute("unknown", {})
        scoped = await rejected.execute("recurrence_concentration_analysis", {"scope": "new"})
        none_arguments = await rejected.execute("recurrence_concentration_analysis")
        assert unknown.outcome == "rejected" and scoped.outcome == "rejected"
        assert none_arguments.outcome == "rejected" and none_arguments.reason == "invalid_arguments"
        assert not any(attempt.executed for attempt in rejected.ledger)

        evaluated: list[str] = []

        def evaluator(name: str) -> AlertOptionalToolSuccess:
            evaluated.append(name)
            return AlertOptionalToolSuccess(name=name, data={})  # type: ignore[arg-type]

        approved = {
            "recurrence_concentration_analysis": lambda: evaluator(
                "recurrence_concentration_analysis"
            ),
            "duration_outlier_analysis": lambda: evaluator("duration_outlier_analysis"),
            "reference_pattern_analysis": lambda: evaluator("reference_pattern_analysis"),
        }
        injected = AlertOptionalToolRegistry(records, _evidence(records), evaluators=approved)
        await injected.execute("recurrence_concentration_analysis", {})
        assert evaluated == ["recurrence_concentration_analysis"]
        with pytest.raises(ValueError, match="exactly the approved names"):
            AlertOptionalToolRegistry(
                records,
                _evidence(records),
                evaluators={
                    **approved,
                    "unregistered": lambda: evaluator("unregistered"),
                },  # type: ignore[dict-item]
            )
        with pytest.raises(ValueError, match="exactly the approved names"):
            AlertOptionalToolRegistry(
                records,
                _evidence(records),
                evaluators={
                    "recurrence_concentration_analysis": approved[
                        "recurrence_concentration_analysis"
                    ],
                },
            )
        assert evaluated == ["recurrence_concentration_analysis"]

    asyncio.run(scenario())


def test_optional_tool_contracts_reject_unknown_and_internal_fields() -> None:
    call = AlertUnsuccessfulToolCall(tool="duration_outlier_analysis", status="timeout")
    assert call.model_dump() == {"tool": "duration_outlier_analysis", "status": "timeout"}
    with pytest.raises(ValidationError):
        AlertUnsuccessfulToolCall.model_validate(
            {"tool": "duration_outlier_analysis", "status": "timeout", "ordinal": 1}
        )
    with pytest.raises(ValidationError):
        AlertUnsuccessfulToolCall.model_validate(
            {"tool": "duration_outlier_analysis", "status": "timeout", "diagnostic": "internal"}
        )
    with pytest.raises(ValidationError):
        AlertOptionalToolExecution.model_validate(
            {"unsuccessful_calls": [call.model_dump()], "ledger": []}
        )


def test_recurrence_concentration_defaults_zero_and_ties() -> None:
    async def scenario() -> None:
        zero = _records((1.0,), (0,))
        assert (
            await AlertOptionalToolRegistry(zero, _evidence(zero)).execute(
                "recurrence_concentration_analysis", {}
            )
        ).outcome == "not_applicable"
        records = _records((1.0, 1.0, 1.0), (None, 5, 5))
        outcome = await AlertOptionalToolRegistry(records, _evidence(records)).execute(
            "recurrence_concentration_analysis", {}
        )
        assert outcome.data["dominant_alert_ids"] == ("id-1", "id-2")
        assert outcome.data["top_record_share"] == 5 / 11

    asyncio.run(scenario())


def test_duration_outlier_minimum_interpolation_and_strict_threshold() -> None:
    async def scenario() -> None:
        undersized = _records((1, 2, 3, 4, 5, 6, 7))
        assert (
            await AlertOptionalToolRegistry(undersized, _evidence(undersized)).execute(
                "duration_outlier_analysis", {}
            )
        ).outcome == "not_applicable"
        records = _records((1, 2, 3, 4, 5, 6, 7, 8, 14.5, 14.6))
        outcome = await AlertOptionalToolRegistry(records, _evidence(records)).execute(
            "duration_outlier_analysis", {}
        )
        assert outcome.data["q1"] == 3.25 and outcome.data["q3"] == 7.75
        assert outcome.data["upper_bound"] == 14.5
        assert outcome.data["outlier_alert_ids"] == ("id-9",)

    asyncio.run(scenario())


def test_reference_pattern_applicability_dominance_and_tie() -> None:
    async def scenario() -> None:
        def comparison(offset: str, direction: str) -> AlertReferenceComparison:
            return AlertReferenceComparison(
                offset=offset,
                occurrence_comparison=AlertOccurrenceComparison(
                    current=2, reference=1, delta=1, direction=direction
                ),
            )

        records = _records((1.0,))
        one = _evidence(records, (comparison("1d", "increased"),))
        assert (
            await AlertOptionalToolRegistry(records, one).execute("reference_pattern_analysis", {})
        ).outcome == "not_applicable"
        unique = _evidence(
            records,
            (
                comparison("1d", "increased"),
                comparison("7d", "increased"),
                comparison("2d", "decreased"),
            ),
        )
        assert (
            await AlertOptionalToolRegistry(records, unique).execute(
                "reference_pattern_analysis", {}
            )
        ).data["dominant_direction"] == "increased"
        tied = _evidence(records, (comparison("1d", "decreased"), comparison("7d", "increased")))
        assert (
            await AlertOptionalToolRegistry(records, tied).execute("reference_pattern_analysis", {})
        ).data["dominant_direction"] == "mixed"

    asyncio.run(scenario())
