"""Strict, framework-neutral Relationship evaluation output contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictRelationshipModel(BaseModel):
    """Base contract that rejects undeclared fields and mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DirectionEvidence(StrictRelationshipModel):
    """One exact comparison of a configured trend direction."""

    lens_id: str = Field(min_length=1)
    property: Literal["trend.direction"] = "trend.direction"
    expected: Literal["increasing", "decreasing", "stable"]
    observed: Literal["increasing", "decreasing", "stable"] | None
    match: bool | None

    @model_validator(mode="after")
    def validate_comparison(self) -> DirectionEvidence:
        """Require unavailable or exactly correlated comparison fields."""

        _validate_comparison(self.expected, self.observed, self.match)
        return self


class RateEvidence(StrictRelationshipModel):
    """One exact comparison of a configured trend rate."""

    lens_id: str = Field(min_length=1)
    property: Literal["trend.rate"] = "trend.rate"
    expected: Literal["slow", "moderate", "fast"]
    observed: Literal["slow", "moderate", "fast", "not_classified"] | None
    match: bool | None

    @model_validator(mode="after")
    def validate_comparison(self) -> RateEvidence:
        """Require unavailable or exactly correlated comparison fields."""

        _validate_comparison(self.expected, self.observed, self.match)
        return self


class VariabilityEvidence(StrictRelationshipModel):
    """One exact comparison of a configured variability state."""

    lens_id: str = Field(min_length=1)
    property: Literal["variability.state"] = "variability.state"
    expected: Literal["low", "moderate", "high"]
    observed: Literal["low", "moderate", "high"] | None
    match: bool | None

    @model_validator(mode="after")
    def validate_comparison(self) -> VariabilityEvidence:
        """Require unavailable or exactly correlated comparison fields."""

        _validate_comparison(self.expected, self.observed, self.match)
        return self


RelationshipEvidence = Annotated[
    DirectionEvidence | RateEvidence | VariabilityEvidence,
    Field(discriminator="property"),
]


class RelationshipEvaluationBase(StrictRelationshipModel):
    """Shared semantic identity and complete evidence for one Relationship."""

    relationship_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None
    conditions: tuple[RelationshipEvidence, ...]
    expectations: tuple[RelationshipEvidence, ...]


class ApplicableRelationshipEvaluation(RelationshipEvaluationBase):
    """Evaluation of a Relationship whose conditions apply."""

    applicability: Literal["applicable"] = "applicable"
    state: Literal["consistent", "inconsistent", "uncertain"]


class NotApplicableRelationshipEvaluation(RelationshipEvaluationBase):
    """Evaluation of a Relationship disproven by condition evidence."""

    applicability: Literal["not_applicable"] = "not_applicable"


class UnknownRelationshipEvaluation(RelationshipEvaluationBase):
    """Evaluation whose applicability cannot be resolved from available evidence."""

    applicability: Literal["unknown"] = "unknown"


RelationshipEvaluation = Annotated[
    (
        ApplicableRelationshipEvaluation
        | NotApplicableRelationshipEvaluation
        | UnknownRelationshipEvaluation
    ),
    Field(discriminator="applicability"),
]


def _validate_comparison(expected: str, observed: str | None, match: bool | None) -> None:
    if observed is None:
        if match is not None:
            raise ValueError("unavailable evidence must use observed=null and match=null")
        return
    if match is None:
        raise ValueError("available evidence requires a Boolean match")
    if match is not (observed == expected):
        raise ValueError("evidence match must equal the exact expected/observed comparison")
