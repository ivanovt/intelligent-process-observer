"""Alert normalization functions owned by the application layer."""

from __future__ import annotations

from app.alerts.contracts import AlertRecordsAvailable


def normalize_empty_current(response: AlertRecordsAvailable) -> tuple[()]:
    """Accept only the successful empty response supported by VS-01."""

    if response.records:
        raise ValueError("non-zero Alert records are outside VS-01")
    return ()
