"""Pure configured-reference windows and current-relative Metric comparisons."""

from __future__ import annotations

from datetime import timedelta

from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricReferenceComparison,
    MetricReferenceEvidence,
    MetricReferenceLevel,
    MetricReferenceTrend,
    MetricReferenceVariability,
    MetricSemantics,
    PreparedUsableSeries,
)


def reference_window(current: MetricAnalysisWindow, offset: str) -> MetricAnalysisWindow:
    """Shift both boundaries backward by one validated configured offset."""

    unit = offset[-1]
    amount = int(offset[:-1])
    multiplier = {"m": 60, "h": 60 * 60, "d": 24 * 60 * 60, "w": 7 * 24 * 60 * 60}[unit]
    shift = timedelta(seconds=amount * multiplier)
    return MetricAnalysisWindow(**{"from": current.from_ - shift, "to": current.to - shift})


def compare_reference(
    *,
    offset: str,
    window: MetricAnalysisWindow,
    current: PreparedUsableSeries,
    current_semantics: MetricSemantics,
    reference: PreparedUsableSeries,
    reference_semantics: MetricSemantics,
) -> tuple[MetricReferenceComparison, MetricReferenceEvidence]:
    """Return one deterministic comparison, oriented as current relative to reference."""

    current_mean = current.evidence.mean
    reference_mean = reference.evidence.mean
    denominator = abs(current_mean) + abs(reference_mean)
    relative_level_change = (
        0.0 if denominator == 0 else 2 * (current_mean - reference_mean) / denominator
    )
    level = (
        "higher"
        if relative_level_change > 0.05
        else "lower"
        if relative_level_change < -0.05
        else "similar"
    )
    current_trend = current_semantics.trend
    reference_trend = reference_semantics.trend
    direction_relation = (
        "not_comparable"
        if "unknown" in {current_trend.direction, reference_trend.direction}
        else "same"
        if current_trend.direction == reference_trend.direction
        else "different"
    )
    rate_relation = _ordered_relation(
        current_trend.rate,
        reference_trend.rate,
        ("slow", "moderate", "fast"),
        higher="faster",
        lower="slower",
    )
    current_variability = current_semantics.variability
    reference_variability = reference_semantics.variability
    variability_relation = _ordered_relation(
        current_variability.state,
        reference_variability.state,
        ("low", "moderate", "high"),
        higher="higher",
        lower="lower",
    )
    comparison = MetricReferenceComparison(
        offset=offset,
        analysis_window=window,
        level=MetricReferenceLevel(relation=level),
        trend=MetricReferenceTrend(
            direction=reference_trend.direction,
            rate=reference_trend.rate,
            direction_relation=direction_relation,
            rate_relation=rate_relation,
        ),
        variability=MetricReferenceVariability(
            state=reference_variability.state,
            relation=variability_relation,
        ),
    )
    evidence = MetricReferenceEvidence(
        offset=offset,
        analysis_window=window,
        **reference.evidence.model_dump(),
        relative_level_change=relative_level_change,
    )
    return comparison, evidence


def _ordered_relation(
    current: str,
    reference: str,
    ordered: tuple[str, ...],
    *,
    higher: str,
    lower: str,
) -> str:
    if current not in ordered or reference not in ordered:
        return "not_comparable"
    current_index = ordered.index(current)
    reference_index = ordered.index(reference)
    if current_index == reference_index:
        return "same" if higher == "faster" else "similar"
    return higher if current_index > reference_index else lower
