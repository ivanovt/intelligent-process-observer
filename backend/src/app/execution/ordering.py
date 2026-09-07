"""Canonical ordering helpers for frozen Observation execution values."""

from __future__ import annotations

from app.execution.contracts import (
    AlertLensSnapshot,
    MetricLensSnapshot,
    ObservationExecutionSnapshot,
)


def canonical_lens_order(
    snapshot: ObservationExecutionSnapshot,
) -> tuple[MetricLensSnapshot | AlertLensSnapshot, ...]:
    """Return Lenses in the fixed Metric-then-Alert, lexical-ID execution order."""

    lenses = (*snapshot.metric_lenses, *snapshot.alert_lenses)
    return tuple(sorted(lenses, key=lambda lens: (_type_rank(lens), lens.lens_id)))


def _type_rank(lens: MetricLensSnapshot | AlertLensSnapshot) -> int:
    """Map supported Lens types to their specified non-lexical ordering rank."""

    return 0 if lens.lens_type == "metric" else 1
