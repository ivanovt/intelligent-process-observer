"""Strict, framework-neutral contracts used by the first Metric pipeline slice."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictMetricModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
_OFFSET_PATTERN = re.compile(r"^[1-9][0-9]*(m|h|d|w)$")


class MetricIdentity(StrictMetricModel):
    observation_id: UUID
    observation_run_id: UUID
    lens_id: str = Field(min_length=1)
    lens_run_id: UUID
    metric_ref: str = Field(min_length=1)
    unit: str = Field(min_length=1)


class MetricAnalysisWindow(StrictMetricModel):
    from_: datetime = Field(alias="from")
    to: datetime

    @field_validator("from_", "to")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return _utc_datetime(value)

    @model_validator(mode="after")
    def ensure_forward_window(self) -> MetricAnalysisWindow:
        if self.from_ >= self.to:
            raise ValueError("analysis_window.from must be before analysis_window.to")
        return self


class MetricProviderScope(StrictMetricModel):
    adapter_type: Literal["prometheus"]
    source_id: str = Field(min_length=1)
    query: str = Field(min_length=1)


class MetricHistoryPolicy(StrictMetricModel):
    lookback_runs: int = Field(default=5, gt=0)
    level_change_tolerance: FiniteFloat = Field(default=0.05, ge=0)


class MetricLensExecutionContext(StrictMetricModel):
    """One already-resolved immutable Metric Lens execution scope."""

    identity: MetricIdentity
    provider_scope: MetricProviderScope
    analysis_window: MetricAnalysisWindow
    analysis_objectives: tuple[str, ...]
    reference_periods: tuple[str, ...]
    history_policy: MetricHistoryPolicy = Field(default_factory=MetricHistoryPolicy)

    @field_validator("reference_periods")
    @classmethod
    def validate_reference_periods(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("reference_periods must not contain duplicates")
        if any(_OFFSET_PATTERN.fullmatch(offset) is None for offset in values):
            raise ValueError("reference_periods must use positive m, h, d, or w offsets")
        return values


class MetricSample(StrictMetricModel):
    timestamp: datetime
    # Acquisition data deliberately admits non-finite values.  Preparation owns
    # their deterministic removal; no public Metric evidence can contain them.
    value: float

    @field_validator("timestamp")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return _utc_datetime(value)


class MetricSeriesAvailable(StrictMetricModel):
    samples: tuple[MetricSample, ...]
    source: Literal["prometheus"]


class MetricSeriesUnavailable(StrictMetricModel):
    """A provider port could not make the requested series available."""

    state: Literal["unavailable"] = "unavailable"
    diagnostic: str = Field(min_length=1, max_length=512)


class MetricSeriesAcquisitionFailure(StrictMetricModel):
    """A provider port failed while acquiring the requested series."""

    state: Literal["failure"] = "failure"
    diagnostic: str = Field(min_length=1, max_length=512)


class MetricSeriesAcquisitionTimeout(StrictMetricModel):
    """A provider port timed out while acquiring the requested series."""

    state: Literal["timeout"] = "timeout"
    diagnostic: str = Field(min_length=1, max_length=512)


MetricSeriesAcquisitionOutcome = (
    MetricSeriesAvailable
    | MetricSeriesUnavailable
    | MetricSeriesAcquisitionFailure
    | MetricSeriesAcquisitionTimeout
)


class MetricCurrentSeriesMalformed(StrictMetricModel):
    """Current series validation rejected duplicate or out-of-window samples."""

    category: Literal["series_malformed"] = "series_malformed"
    diagnostic: str = Field(min_length=1, max_length=512)


class MetricMandatoryAnalysisFailure(StrictMetricModel):
    """An unexpected mandatory calculation, semantic, or result-build failure."""

    category: Literal["mandatory_analysis"] = "mandatory_analysis"
    diagnostic: str = Field(min_length=1, max_length=512)


class MetricCurrentAcquisitionFailed(StrictMetricModel):
    """A current provider outcome could not produce usable data."""

    category: Literal["acquisition"] = "acquisition"
    diagnostic: str = Field(min_length=1, max_length=512)


MetricCurrentFailure = (
    MetricCurrentAcquisitionFailed | MetricCurrentSeriesMalformed | MetricMandatoryAnalysisFailure
)


class MetricEvidence(StrictMetricModel):
    mean: FiniteFloat
    std: FiniteFloat = Field(ge=0)
    min: FiniteFloat
    max: FiniteFloat
    slope: FiniteFloat


class MetricTrend(StrictMetricModel):
    direction: Literal["increasing", "decreasing", "stable"]
    rate: Literal["slow", "moderate", "fast", "not_classified"]

    @model_validator(mode="after")
    def correlate_direction_and_rate(self) -> MetricTrend:
        stable = self.direction == "stable"
        if stable != (self.rate == "not_classified"):
            raise ValueError("stable trend must use not_classified rate")
        return self


class MetricVariability(StrictMetricModel):
    state: Literal["low", "moderate", "high"]


class MetricSemantics(StrictMetricModel):
    trend: MetricTrend
    variability: MetricVariability


class PreparedGoodSeries(StrictMetricModel):
    data_quality: Literal["good"]
    samples: tuple[MetricSample, ...]
    evidence: MetricEvidence
    residuals: tuple[FiniteFloat, ...]


class PreparedDegradedSeries(StrictMetricModel):
    data_quality: Literal["degraded"]
    samples: tuple[MetricSample, ...]
    evidence: MetricEvidence
    residuals: tuple[FiniteFloat, ...]


class PreparedInsufficientSeries(StrictMetricModel):
    """A successful quality determination with no mandatory analytical core."""

    data_quality: Literal["insufficient"]
    samples: tuple[MetricSample, ...]


PreparedUsableSeries = PreparedGoodSeries | PreparedDegradedSeries
PreparedSeries = PreparedUsableSeries | PreparedInsufficientSeries


class SpikeToolDescriptor(StrictMetricModel):
    name: Literal["spike"] = "spike"
    capability: Literal["isolated_extreme_detection"] = "isolated_extreme_detection"
    minimum_samples: Literal[5] = 5


class OscillationToolDescriptor(StrictMetricModel):
    name: Literal["oscillation"] = "oscillation"
    capability: Literal["detrended_residual_alternation"] = "detrended_residual_alternation"
    minimum_samples: Literal[8] = 8


class StuckSignalToolDescriptor(StrictMetricModel):
    name: Literal["stuck_signal"] = "stuck_signal"
    capability: Literal["exact_repeated_value_run_detection"] = "exact_repeated_value_run_detection"
    minimum_samples: Literal[5] = 5


MetricToolDescriptors = tuple[
    SpikeToolDescriptor,
    OscillationToolDescriptor,
    StuckSignalToolDescriptor,
]
FIXED_ALLOWED_TOOLS: MetricToolDescriptors = (
    SpikeToolDescriptor(),
    OscillationToolDescriptor(),
    StuckSignalToolDescriptor(),
)


class MetricAgentUsableRequest(StrictMetricModel):
    identity: MetricIdentity
    analysis_window: MetricAnalysisWindow
    analysis_objectives: tuple[str, ...]
    data_quality: Literal["good", "degraded"]
    evidence: MetricEvidence
    semantics: MetricSemantics
    allowed_tools: MetricToolDescriptors
    dataset_ref: str = Field(min_length=1)

    @field_validator("allowed_tools")
    @classmethod
    def require_fixed_descriptors(cls, value: MetricToolDescriptors) -> MetricToolDescriptors:
        if value != FIXED_ALLOWED_TOOLS:
            raise ValueError("allowed_tools must be the fixed ordered Metric registry")
        return value


class MetricAgentInsufficientRequest(StrictMetricModel):
    identity: MetricIdentity
    analysis_window: MetricAnalysisWindow
    data_quality: Literal["insufficient"]


class MetricAgentCompletion(StrictMetricModel):
    state: Literal["completed"] = "completed"


class MetricAgentOperationalFailure(StrictMetricModel):
    """Transient insufficient-agent failure; it never becomes public result data."""

    state: Literal["operational_failure"] = "operational_failure"


MetricAgentRequest = MetricAgentUsableRequest | MetricAgentInsufficientRequest
MetricAgentOutcome = MetricAgentCompletion | MetricAgentOperationalFailure


class MetricHistoryEmpty(StrictMetricModel):
    """Successful History read with no eligible prior Metric results."""

    state: Literal["empty"] = "empty"


class MetricCurrentState(StrictMetricModel):
    trend: MetricTrend
    variability: MetricVariability


class MetricResultProvenance(StrictMetricModel):
    source: Literal["prometheus"]
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return _utc_datetime(value)


class MetricCompletedStatus(StrictMetricModel):
    state: Literal["completed"] = "completed"


class CurrentMetricAcquisitionFailedError(StrictMetricModel):
    code: Literal["current_metric_acquisition_failed"] = "current_metric_acquisition_failed"
    message: Literal["Current metric data acquisition failed."] = (
        "Current metric data acquisition failed."
    )


class CurrentMetricSeriesMalformedError(StrictMetricModel):
    code: Literal["current_metric_series_malformed"] = "current_metric_series_malformed"
    message: Literal["Current metric series is malformed."] = "Current metric series is malformed."


class MandatoryMetricAnalysisFailedError(StrictMetricModel):
    code: Literal["mandatory_metric_analysis_failed"] = "mandatory_metric_analysis_failed"
    message: Literal["Mandatory metric analysis failed."] = "Mandatory metric analysis failed."


MetricFailedError = (
    CurrentMetricAcquisitionFailedError
    | CurrentMetricSeriesMalformedError
    | MandatoryMetricAnalysisFailedError
)


class MetricFailedStatus(StrictMetricModel):
    state: Literal["failed"] = "failed"
    error: Annotated[MetricFailedError, Field(discriminator="code")]


class MetricCurrentEvidence(StrictMetricModel):
    mean: FiniteFloat
    std: FiniteFloat = Field(ge=0)
    min: FiniteFloat
    max: FiniteFloat
    slope: FiniteFloat


class MetricEvidenceSection(StrictMetricModel):
    current: MetricCurrentEvidence


class CompletedSufficientMetricResult(StrictMetricModel):
    schema_version: Literal["1.0"] = "1.0"
    lens_type: Literal["metric"] = "metric"
    identity: MetricIdentity
    status: MetricCompletedStatus = Field(default_factory=MetricCompletedStatus)
    analysis_window: MetricAnalysisWindow
    data_quality: Literal["good", "degraded"]
    current_state: MetricCurrentState
    evidence: MetricEvidenceSection
    provenance: MetricResultProvenance


class CompletedInsufficientMetricResult(StrictMetricModel):
    schema_version: Literal["1.0"] = "1.0"
    lens_type: Literal["metric"] = "metric"
    identity: MetricIdentity
    status: MetricCompletedStatus = Field(default_factory=MetricCompletedStatus)
    analysis_window: MetricAnalysisWindow
    data_quality: Literal["insufficient"]
    provenance: MetricResultProvenance


class FailedMetricResult(StrictMetricModel):
    """Traceability-only result for an unproducible mandatory current core."""

    schema_version: Literal["1.0"] = "1.0"
    lens_type: Literal["metric"] = "metric"
    identity: MetricIdentity
    status: MetricFailedStatus
    analysis_window: MetricAnalysisWindow
    provenance: MetricResultProvenance


def assert_finite_public_numbers(value: object) -> None:
    """Defensive boundary for callers that pass native values into strict models."""

    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Metric public numbers must be finite")
