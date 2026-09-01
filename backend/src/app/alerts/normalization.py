"""Alert lifecycle normalization functions owned by the application layer."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from pydantic import ValidationError

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
    """Retain valid unique overlap records for existing deterministic consumers."""
    return normalize_current_with_rejections(response, window, analysis_timestamp)[0]


def normalize_current_with_rejections(
    response: AlertRecordsAvailable, window: AlertAnalysisWindow, analysis_timestamp: datetime
) -> tuple[tuple[CanonicalAlertRecord, ...], bool]:
    """Retain valid unique overlap records and report rejected provider values."""
    parsed: list[AlertProviderRecord] = []
    rejected = False
    for raw in response.records:
        try:
            parsed.append(AlertProviderRecord.model_validate(raw))
        except ValidationError:
            rejected = True
    duplicate_ids = {
        identifier for identifier, count in Counter(item.id for item in parsed).items() if count > 1
    }
    rejected = rejected or bool(duplicate_ids)
    return (
        tuple(
            CanonicalAlertRecord(
                id=r.id,
                title=r.title,
                description=r.description,
                started_at=r.started_at,
                ended_at=r.ended_at,
                duration_seconds=(
                    (r.ended_at or analysis_timestamp) - r.started_at
                ).total_seconds(),
                status=AlertStatus(
                    normalized="resolved" if r.ended_at else "active", source=r.source_status
                ),
                provider_importance=r.provider_importance,
                occurrence_count=r.occurrence_count,
                source_ref=r.source_ref,
            )
            for r in parsed
            if r.id not in duplicate_ids and _overlaps(r, window)
        ),
        rejected,
    )


def _overlaps(record: AlertProviderRecord, window: AlertAnalysisWindow) -> bool:
    """Apply the approved strict lifecycle-overlap membership formula."""
    return record.started_at < window.to and (
        record.ended_at is None or record.ended_at > window.from_
    )
