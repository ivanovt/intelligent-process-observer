"""Bounded deterministic optional tools for one prepared Alert run."""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable
from inspect import isawaitable

from app.alerts.contracts import (
    FIXED_ALERT_OPTIONAL_TOOLS,
    AlertMandatoryEvidence,
    AlertOptionalToolAttempt,
    AlertOptionalToolExecutionOutcome,
    AlertOptionalToolFailed,
    AlertOptionalToolName,
    AlertOptionalToolNotApplicable,
    AlertOptionalToolOutcome,
    AlertOptionalToolRejected,
    AlertOptionalToolSuccess,
    AlertOptionalToolTimedOut,
    CanonicalAlertRecord,
)

ToolEvaluator = Callable[
    [], AlertOptionalToolExecutionOutcome | Awaitable[AlertOptionalToolExecutionOutcome]
]


def recurrence_concentration(
    records: tuple[CanonicalAlertRecord, ...], evidence: AlertMandatoryEvidence
) -> AlertOptionalToolExecutionOutcome:
    """Calculate the top effective-occurrence share across current records."""
    total = evidence.occurrence_count
    name: AlertOptionalToolName = "recurrence_concentration_analysis"
    if total == 0:
        return AlertOptionalToolNotApplicable(name=name)
    counts = {
        record.id: record.occurrence_count if record.occurrence_count is not None else 1
        for record in records
    }
    maximum = max(counts.values())
    dominant_ids = tuple(
        sorted(identifier for identifier, count in counts.items() if count == maximum)
    )
    return AlertOptionalToolSuccess(
        name=name,
        data={
            "dominant_alert_ids": dominant_ids,
            "dominant_occurrence_count": maximum,
            "total_occurrence_count": total,
            "top_record_share": maximum / total,
        },
    )


def duration_outliers(
    records: tuple[CanonicalAlertRecord, ...],
) -> AlertOptionalToolExecutionOutcome:
    """Find strict high-side IQR duration outliers from at least eight records."""
    name: AlertOptionalToolName = "duration_outlier_analysis"
    durations = sorted(record.duration_seconds for record in records)
    if len(durations) < 8:
        return AlertOptionalToolNotApplicable(
            name=name,
            data={
                "reason": "insufficient_sample",
                "sample_size": len(durations),
                "minimum_required": 8,
            },
        )
    q1, q3 = _percentile(durations, 0.25), _percentile(durations, 0.75)
    upper_bound = q3 + 1.5 * (q3 - q1)
    outlier_ids = tuple(record.id for record in records if record.duration_seconds > upper_bound)
    return AlertOptionalToolSuccess(
        name=name,
        data={"q1": q1, "q3": q3, "upper_bound": upper_bound, "outlier_alert_ids": outlier_ids},
    )


def reference_pattern(evidence: AlertMandatoryEvidence) -> AlertOptionalToolExecutionOutcome:
    """Summarize the dominant direction across successful reference comparisons."""
    name: AlertOptionalToolName = "reference_pattern_analysis"
    comparisons = evidence.comparisons
    if len(comparisons) < 2:
        return AlertOptionalToolNotApplicable(name=name)
    counts = Counter(item.occurrence_comparison.direction for item in comparisons)
    maximum = max(counts.values())
    winners = [direction for direction, count in counts.items() if count == maximum]
    return AlertOptionalToolSuccess(
        name=name,
        data={
            "compared_periods": len(comparisons),
            "directions": {
                direction: counts.get(direction, 0)
                for direction in ("increased", "decreased", "unchanged")
            },
            "dominant_direction": winners[0] if len(winners) == 1 else "mixed",
        },
    )


class AlertOptionalToolRegistry:
    """Own immutable Alert data and the authoritative ten-attempt optional-tool ledger."""

    descriptors = FIXED_ALERT_OPTIONAL_TOOLS

    def __init__(
        self,
        records: tuple[CanonicalAlertRecord, ...],
        evidence: AlertMandatoryEvidence,
        evaluators: dict[AlertOptionalToolName, ToolEvaluator] | None = None,
    ) -> None:
        self._records, self._evidence = records, evidence
        self._attempts: list[AlertOptionalToolAttempt] = []
        self._evaluators: dict[AlertOptionalToolName, ToolEvaluator] = {
            "recurrence_concentration_analysis": lambda: recurrence_concentration(
                records, evidence
            ),
            "duration_outlier_analysis": lambda: duration_outliers(records),
            "reference_pattern_analysis": lambda: reference_pattern(evidence),
        }
        if evaluators is not None:
            if set(evaluators) != set(self._evaluators):
                raise ValueError("optional-tool evaluators must cover exactly the approved names")
            self._evaluators = evaluators

    @property
    def ledger(self) -> tuple[AlertOptionalToolAttempt, ...]:
        """Return the internal ordered attempt ledger."""
        return tuple(self._attempts)

    async def execute(self, name: str, arguments: object = None) -> AlertOptionalToolOutcome:
        """Admit an empty-object request before evaluating its immutable binding."""
        ordinal = len(self._attempts) + 1
        if len(self._attempts) >= 10:
            return self._rejected(name, ordinal, "over_budget")
        if name not in self._evaluators:
            return self._rejected(name, ordinal, "unregistered")
        if not isinstance(arguments, dict) or arguments:
            return self._rejected(name, ordinal, "invalid_arguments")
        registered_name: AlertOptionalToolName = name
        try:
            outcome = self._evaluators[registered_name]()
            if isawaitable(outcome):
                outcome = await outcome
        except TimeoutError as error:
            outcome = AlertOptionalToolTimedOut(name=registered_name, diagnostic=_diagnostic(error))
        except Exception as error:
            outcome = AlertOptionalToolFailed(name=registered_name, diagnostic=_diagnostic(error))
        self._attempts.append(
            AlertOptionalToolAttempt(
                ordinal=ordinal, requested_name=name, outcome=outcome, executed=True
            )
        )
        return outcome

    def _rejected(self, name: str, ordinal: int, reason: str) -> AlertOptionalToolRejected:
        outcome = AlertOptionalToolRejected(reason=reason)  # type: ignore[arg-type]
        self._attempts.append(
            AlertOptionalToolAttempt(
                ordinal=ordinal, requested_name=name, outcome=outcome, executed=False
            )
        )
        return outcome


def unsuccessful_trace(ledger: tuple[AlertOptionalToolAttempt, ...]) -> tuple[dict[str, str], ...]:
    """Project only failed and timed-out calls for the public result builder."""
    return tuple(
        {"tool": attempt.outcome.name, "status": attempt.outcome.outcome}
        for attempt in ledger
        if isinstance(attempt.outcome, (AlertOptionalToolFailed, AlertOptionalToolTimedOut))
    )


def _percentile(values: list[float], percentile: float) -> float:
    index = (len(values) - 1) * percentile
    lower, upper = int(index), int(index) + (index % 1 > 0)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def _diagnostic(error: BaseException) -> str:
    return (str(error).strip() or type(error).__name__)[:512]
