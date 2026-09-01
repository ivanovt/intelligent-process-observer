"""Deterministic mandatory Alert evidence calculations."""

from __future__ import annotations

from app.alerts.contracts import AlertMandatoryEvidence


def analyze_zero_records(records: tuple[()]) -> AlertMandatoryEvidence:
    """Produce the exact mandatory evidence for a successful empty current dataset."""

    if records:
        raise ValueError("non-zero Alert records are outside VS-01")
    return AlertMandatoryEvidence()
