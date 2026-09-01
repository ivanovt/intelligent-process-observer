"""Alert lifecycle normalization functions owned by the application layer."""

from __future__ import annotations

from datetime import datetime

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertProviderRecord,
    AlertRecordsAvailable,
    AlertStatus,
    CanonicalAlertRecord,
)


def normalize_current(
    response: AlertRecordsAvailable, window: AlertAnalysisWindow, analysis_timestamp: datetime
) -> tuple[CanonicalAlertRecord, ...]:
    """Retain only records with strict lifecycle overlap and canonical full durations."""
    return tuple(
        CanonicalAlertRecord(
            id=r.id,
            title=r.title,
            description=r.description,
            started_at=r.started_at,
            ended_at=r.ended_at,
            duration_seconds=((r.ended_at or analysis_timestamp) - r.started_at).total_seconds(),
            status=AlertStatus(
                normalized="resolved" if r.ended_at else "active", source=r.source_status
            ),
            provider_importance=r.provider_importance,
            occurrence_count=r.occurrence_count,
            source_ref=r.source_ref,
        )
        for r in response.records
        if _overlaps(r, window)
    )


def _overlaps(record: AlertProviderRecord, window: AlertAnalysisWindow) -> bool:
    """Apply the approved strict lifecycle-overlap membership formula."""
    return record.started_at < window.to and (
        record.ended_at is None or record.ended_at > window.from_
    )
