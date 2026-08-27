"""Pure current-series preparation and deterministic mandatory statistics."""

from __future__ import annotations

import math

from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricEvidence,
    MetricSample,
    PreparedDegradedSeries,
    PreparedGoodSeries,
    PreparedInsufficientSeries,
    PreparedSeries,
)


def prepare_series(
    samples: tuple[MetricSample, ...], window: MetricAnalysisWindow
) -> PreparedSeries:
    """Validate, filter, classify, and analyze one acquired Metric series.

    Duplicate and out-of-window inputs remain malformed technical conditions.  NaN and
    infinities are instead removed before the deterministic quality assessment.
    """

    if any(sample.timestamp < window.from_ or sample.timestamp > window.to for sample in samples):
        raise ValueError("Metric sample is outside the analysis window")
    ordered_samples = tuple(sorted(samples, key=lambda sample: sample.timestamp))
    if len({sample.timestamp for sample in ordered_samples}) != len(ordered_samples):
        raise ValueError("Metric samples must have unique timestamps")
    ordered = tuple(sample for sample in ordered_samples if math.isfinite(sample.value))
    if len(ordered) < 3:
        return PreparedInsufficientSeries(data_quality="insufficient", samples=ordered)

    values = tuple(sample.value for sample in ordered)
    value_scale = max(abs(value) for value in values)
    normalized_values = tuple(value / value_scale for value in values) if value_scale else values
    normalized_mean = math.fsum(value / len(values) for value in normalized_values)
    mean = normalized_mean * value_scale
    normalized_variance = math.fsum(
        (value - normalized_mean) ** 2 / len(values) for value in normalized_values
    )
    std = math.sqrt(normalized_variance) * value_scale
    elapsed = tuple((sample.timestamp - window.from_).total_seconds() for sample in ordered)
    x_mean = math.fsum(elapsed) / len(elapsed)
    numerator = math.fsum(
        (x - x_mean) * (y - normalized_mean)
        for x, y in zip(elapsed, normalized_values, strict=True)
    )
    denominator = math.fsum((x - x_mean) ** 2 for x in elapsed)
    if denominator == 0:
        raise ValueError("Metric samples must have distinct elapsed timestamps")
    slope = numerator / denominator * value_scale
    fitted_normalized = tuple(
        normalized_mean + (numerator / denominator) * (x - x_mean) for x in elapsed
    )
    residuals = tuple(
        (value - estimate) * value_scale
        for value, estimate in zip(normalized_values, fitted_normalized, strict=True)
    )
    if not all(math.isfinite(value) for value in (*values, mean, std, slope, *residuals)):
        raise ValueError("Metric mandatory evidence must remain finite")
    evidence = MetricEvidence(mean=mean, std=std, min=min(values), max=max(values), slope=slope)
    if len(ordered) == len(ordered_samples):
        return PreparedGoodSeries(
            data_quality="good", samples=ordered, evidence=evidence, residuals=residuals
        )
    return PreparedDegradedSeries(
        data_quality="degraded", samples=ordered, evidence=evidence, residuals=residuals
    )
