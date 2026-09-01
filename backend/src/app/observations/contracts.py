from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_-]*$"
OFFSET_PATTERN = r"^[1-9][0-9]*(m|h|d|w)$"


class AnalysisObjective(StrEnum):
    SPIKE = "spike"
    DRIFT = "drift"
    OSCILLATION = "oscillation"


class TrendDirection(StrEnum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


class TrendRate(StrEnum):
    SLOW = "slow"
    MODERATE = "moderate"
    FAST = "fast"


class VariabilityState(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrendDescriptor(ApiModel):
    direction: TrendDirection | None = None
    rate: TrendRate | None = None

    @model_validator(mode="after")
    def has_value(self) -> TrendDescriptor:
        if self.direction is None and self.rate is None:
            raise ValueError("trend must define direction or rate")
        return self


class VariabilityDescriptor(ApiModel):
    state: VariabilityState


class SemanticDescriptor(ApiModel):
    trend: TrendDescriptor | None = None
    variability: VariabilityDescriptor | None = None

    @model_validator(mode="after")
    def has_value(self) -> SemanticDescriptor:
        if self.trend is None and self.variability is None:
            raise ValueError("descriptor must define trend or variability")
        return self


class MetricLensCreate(ApiModel):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=1)
    description: str | None = None
    type: Literal["metric"]
    metric_id: str = Field(min_length=1)
    adapter_type: Literal["prometheus"]
    source_id: str = Field(pattern=IDENTIFIER_PATTERN)
    query: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    analysis_objectives: list[AnalysisObjective]
    reference_periods: list[str]

    @model_validator(mode="after")
    def validate_lists(self) -> MetricLensCreate:
        if len(set(self.analysis_objectives)) != len(self.analysis_objectives):
            raise ValueError("analysis_objectives must not contain duplicates")
        if len(set(self.reference_periods)) != len(self.reference_periods):
            raise ValueError("reference_periods must not contain duplicates")
        for offset in self.reference_periods:
            if not re.fullmatch(OFFSET_PATTERN, offset):
                raise ValueError("reference_periods must use positive m, h, d, or w offsets")
        return self


class AlertApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class AlertSelectorCreate(AlertApiModel):
    query: str = Field(min_length=1)


class AlertLensCreate(AlertApiModel):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=1)
    description: str | None = None
    type: Literal["alert"]
    source: Literal["jira_track_and_release"]
    selector: AlertSelectorCreate
    analysis_objectives: list[str] = Field(default_factory=list)
    reference_periods: list[str] = Field(default_factory=list)


class RelationshipCreate(ApiModel):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=1)
    description: str | None = None
    participants: list[str] = Field(min_length=2)
    conditions: dict[str, SemanticDescriptor] = Field(default_factory=dict)
    expected: dict[str, SemanticDescriptor] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_participants(self) -> RelationshipCreate:
        if len(set(self.participants)) != len(self.participants):
            raise ValueError("participants must not contain duplicates")
        referenced = set(self.conditions) | set(self.expected)
        participant_set = set(self.participants)
        if not referenced.issubset(participant_set):
            raise ValueError("conditions and expected keys must be participants")
        if not participant_set.issubset(referenced):
            raise ValueError("every participant must be used by conditions or expected")
        return self


class ObservationCreate(ApiModel):
    name: str = Field(min_length=1)
    description: str | None = None
    objective: str = Field(min_length=1)
    lenses: list[MetricLensCreate] = Field(default_factory=list)
    alert_lenses: list[AlertLensCreate] = Field(default_factory=list)
    relationships: list[RelationshipCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_topology(self) -> ObservationCreate:
        if not self.lenses and not self.alert_lenses:
            raise ValueError("Observation definition must contain at least one Lens")
        lens_ids = [lens.id for lens in self.lenses]
        if len(set(lens_ids)) != len(lens_ids):
            raise ValueError("lens IDs must be unique")
        relationship_ids = [relationship.id for relationship in self.relationships]
        if len(set(relationship_ids)) != len(relationship_ids):
            raise ValueError("relationship IDs must be unique")
        known_lenses = set(lens_ids)
        for relationship in self.relationships:
            unknown = set(relationship.participants) - known_lenses
            if unknown:
                raise ValueError(
                    "relationship participants must reference Observation Metric Lenses"
                )
        return self


class LensReference(ApiModel):
    id: str
    name: str
    type: Literal["metric"]
    href: str


class AlertLensReference(ApiModel):
    id: str
    name: str
    type: Literal["alert"]
    href: str


class RelationshipReference(ApiModel):
    id: str
    name: str
    href: str


class ObservationSummary(ApiModel):
    id: UUID
    name: str
    description: str | None
    objective: str
    schema_version: int
    lenses: list[LensReference]
    alert_lenses: list[AlertLensReference] = Field(default_factory=list)
    relationships: list[RelationshipReference]
    href: str


class MetricLensResponse(MetricLensCreate):
    href: str
    observation_href: str


class AlertLensResponse(AlertLensCreate):
    href: str
    observation_href: str


class RelationshipResponse(RelationshipCreate):
    href: str
    observation_href: str


class ObservationResponse(ObservationSummary):
    lenses: list[MetricLensResponse]
    alert_lenses: list[AlertLensResponse] = Field(default_factory=list)
    relationships: list[RelationshipResponse]


class CapabilitySource(ApiModel):
    id: str
    name: str


class CapabilityAdapter(ApiModel):
    adapter_type: Literal["prometheus"]
    sources: list[CapabilitySource]


class DefinitionCapabilities(ApiModel):
    metric: list[CapabilityAdapter]


class ValidationWindow(ApiModel):
    duration: str = Field(pattern=OFFSET_PATTERN)


class MetricPreflightRequest(ApiModel):
    source_id: str = Field(pattern=IDENTIFIER_PATTERN)
    query: str = Field(min_length=1)
    validation_window: ValidationWindow


class MetricSample(ApiModel):
    timestamp: str
    value: float | None
    value_status: Literal["finite", "nan", "positive_infinity", "negative_infinity"]


class MetricPreflightSuccess(ApiModel):
    valid: Literal[True]
    resolved_start: str
    resolved_end: str
    step_seconds: int
    labels: dict[str, str]
    samples: list[MetricSample]
    warnings: list[str]


class MetricPreflightFailure(ApiModel):
    valid: Literal[False]
    code: str
    message: str
    series_count: int | None = None
    label_sets: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


MetricPreflightResponse = Annotated[
    MetricPreflightSuccess | MetricPreflightFailure,
    Field(discriminator="valid"),
]
