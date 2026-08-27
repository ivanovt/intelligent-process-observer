"""Pure current-series preparation and deterministic mandatory statistics."""

from __future__ import annotations

import math

from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricEvidence,
    MetricSample,
    PreparedGoodSeries,
)


def prepare_good_series(
    samples: tuple[MetricSample, ...], window: MetricAnalysisWindow
) -> PreparedGoodSeries:
    """Validate one known-good finite series and calculate its mandatory evidence.

    Degraded, insufficient, and malformed outcomes deliberately enter in later slices;
    this first walking skeleton accepts only the approved representative good path.
    """

    if any(sample.timestamp < window.from_ or sample.timestamp > window.to for sample in samples):
        raise ValueError("Metric sample is outside the analysis window")
    ordered = tuple(sorted(samples, key=lambda sample: sample.timestamp))
    if len({sample.timestamp for sample in ordered}) != len(ordered):
        raise ValueError("Metric samples must have unique timestamps")
    if len(ordered) < 3:
        raise ValueError("VS-01 requires at least three finite Metric samples")

    values = tuple(sample.value for sample in ordered)
    mean = math.fsum(values) / len(values)
    variance = math.fsum((value - mean) ** 2 for value in values) / len(values)
    std = math.sqrt(variance)
    elapsed = tuple((sample.timestamp - window.from_).total_seconds() for sample in ordered)
    x_mean = math.fsum(elapsed) / len(elapsed)
    numerator = math.fsum((x - x_mean) * (y - mean) for x, y in zip(elapsed, values, strict=True))
    denominator = math.fsum((x - x_mean) ** 2 for x in elapsed)
    if denominator == 0:
        raise ValueError("Metric samples must have distinct elapsed timestamps")
    slope = numerator / denominator
    fitted = tuple(mean + slope * (x - x_mean) for x in elapsed)
    residuals = tuple(y - estimate for y, estimate in zip(values, fitted, strict=True))
    evidence = MetricEvidence(mean=mean, std=std, min=min(values), max=max(values), slope=slope)
    return PreparedGoodSeries(
        data_quality="good", samples=ordered, evidence=evidence, residuals=residuals
    )
