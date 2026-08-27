"""ADR-153 normalized mandatory Metric semanticization."""

from __future__ import annotations

import math

from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricSemantics,
    MetricTrend,
    MetricVariability,
    PreparedGoodSeries,
)


def semanticize_mandatory(
    prepared: PreparedGoodSeries, window: MetricAnalysisWindow
) -> MetricSemantics:
    evidence = prepared.evidence
    duration = (window.to - window.from_).total_seconds()
    scale = max(abs(evidence.mean), evidence.max - evidence.min)
    if scale == 0:
        return MetricSemantics(
            trend=MetricTrend(direction="stable", rate="not_classified"),
            variability=MetricVariability(state="low"),
        )
    normalized_trend = abs(evidence.slope) * duration / scale
    residual_std = math.sqrt(
        math.fsum(residual**2 for residual in prepared.residuals) / len(prepared.residuals)
    )
    normalized_variability = residual_std / scale
    if normalized_trend < 0.05:
        trend = MetricTrend(direction="stable", rate="not_classified")
    else:
        direction = "increasing" if evidence.slope > 0 else "decreasing"
        rate = (
            "slow" if normalized_trend < 0.15 else "moderate" if normalized_trend < 0.35 else "fast"
        )
        trend = MetricTrend(direction=direction, rate=rate)
    variability = MetricVariability(
        state="low"
        if normalized_variability < 0.05
        else "moderate"
        if normalized_variability < 0.15
        else "high"
    )
    return MetricSemantics(trend=trend, variability=variability)
