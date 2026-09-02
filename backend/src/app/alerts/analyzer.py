"""Deterministic mandatory Alert evidence calculations."""

from __future__ import annotations

from collections import Counter

from app.alerts.contracts import (
    AlertActivity,
    AlertDurationStatistics,
    AlertMandatoryEvidence,
    AlertOccurrenceComparison,
    AlertProviderImportanceDistribution,
    AlertReferenceComparison,
    AlertStatusDistribution,
    CanonicalAlertRecord,
)


def analyze_current(records: tuple[CanonicalAlertRecord, ...]) -> AlertMandatoryEvidence:
    """Produce reproducible activity, status, duration, and native importance evidence."""
    occurrences = sum(r.occurrence_count if r.occurrence_count is not None else 1 for r in records)
    statuses, durations = (
        Counter(r.status.normalized for r in records),
        [r.duration_seconds for r in records],
    )
    importance = [r.provider_importance for r in records if r.provider_importance]
    distribution = None
    if importance:
        if len({item.type for item in importance}) != 1:
            raise ValueError("mixed provider importance types are outside VS-02")
        distribution = AlertProviderImportanceDistribution(
            type=importance[0].type, values=dict(Counter(item.value for item in importance))
        )
    return AlertMandatoryEvidence(
        alert_activity=AlertActivity(record_count=len(records), occurrence_count=occurrences),
        status_distribution=AlertStatusDistribution(
            active=statuses["active"], resolved=statuses["resolved"], unknown=statuses["unknown"]
        ),
        duration_statistics=AlertDurationStatistics(
            min_seconds=min(durations),
            max_seconds=max(durations),
            average_seconds=sum(durations) / len(durations),
        )
        if durations
        else None,
        provider_importance_distribution=distribution,
    )


def compare_occurrences(
    offset: str, current: AlertMandatoryEvidence, reference: AlertMandatoryEvidence
) -> AlertReferenceComparison:
    """Project one successful reference period as current-relative occurrence evidence."""
    delta = current.occurrence_count - reference.occurrence_count
    return AlertReferenceComparison(
        offset=offset,
        occurrence_comparison=AlertOccurrenceComparison(
            current=current.occurrence_count,
            reference=reference.occurrence_count,
            delta=delta,
            direction="increased" if delta > 0 else "decreased" if delta < 0 else "unchanged",
        ),
    )
