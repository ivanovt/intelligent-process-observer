"""Independent configured reference acquisition for Alert occurrence comparisons."""

from __future__ import annotations

from datetime import timedelta

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertProviderScope,
    AlertRecordsAvailable,
    CanonicalAlertRecord,
)
from app.alerts.normalization import normalize_current_with_rejections
from app.alerts.ports import AlertProvider


def reference_window(current: AlertAnalysisWindow, offset: str) -> AlertAnalysisWindow:
    """Return the same-duration current window shifted backward by its offset."""
    multiplier = {"m": 60, "h": 3600, "d": 86400, "w": 604800}[offset[-1]]
    shift = timedelta(seconds=int(offset[:-1]) * multiplier)
    return AlertAnalysisWindow(**{"from": current.from_ - shift, "to": current.to - shift})


async def acquire_prepared_references(
    provider: AlertProvider,
    scope: AlertProviderScope,
    current_window: AlertAnalysisWindow,
    offsets: tuple[str, ...],
) -> tuple[tuple[tuple[str, tuple[CanonicalAlertRecord, ...]], ...], bool]:
    """Acquire and normalize each configured reference period independently."""
    prepared_references: list[tuple[str, tuple[CanonicalAlertRecord, ...]]] = []
    unavailable = False
    for offset in offsets:
        window = reference_window(current_window, offset)
        try:
            response = await provider.acquire(scope, window)
        except Exception:
            unavailable = True
            continue
        if not isinstance(response, AlertRecordsAvailable):
            unavailable = True
            continue
        records, rejected = normalize_current_with_rejections(response, window, window.to)
        if rejected or (response.records and not records):
            unavailable = True
            continue
        prepared_references.append((offset, records))
    return tuple(prepared_references), unavailable
