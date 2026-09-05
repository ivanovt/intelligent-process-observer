"""Pure deterministic evaluation of configured Metric relationships."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from pydantic import ValidationError

from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensRunStatus,
    LensType,
)
from app.metrics.contracts import (
    CompletedInsufficientMetricResult,
    CompletedSufficientMetricResult,
    FailedMetricResult,
    MetricCurrentState,
    PartialMetricResult,
)
from app.observations.contracts import RelationshipCreate, SemanticDescriptor
from app.relationships.contracts import (
    ApplicableRelationshipEvaluation,
    DirectionEvidence,
    NotApplicableRelationshipEvaluation,
    RateEvidence,
    RelationshipEvaluation,
    RelationshipEvidence,
    UnknownRelationshipEvaluation,
    VariabilityEvidence,
)

_MetricResult = (
    CompletedSufficientMetricResult
    | CompletedInsufficientMetricResult
    | PartialMetricResult
    | FailedMetricResult
)


class RelationshipEvaluator:
    """Evaluate ordered Relationship definitions against complete Lens result batches."""

    def evaluate(
        self,
        relationships: Sequence[RelationshipCreate],
        results: Sequence[LensAnalysisResultInput],
    ) -> tuple[RelationshipEvaluation, ...]:
        """Return one validated evaluation per Relationship without side effects."""

        _validate_relationship_ids(relationships)
        metric_envelopes = _index_metric_envelopes(results)
        current_states = _resolve_current_states(relationships, metric_envelopes)
        return tuple(
            _evaluate_relationship(relationship, current_states) for relationship in relationships
        )


def _validate_relationship_ids(relationships: Sequence[RelationshipCreate]) -> None:
    relationship_ids = [relationship.id for relationship in relationships]
    if len(relationship_ids) != len(set(relationship_ids)):
        raise ValueError("relationship IDs must not contain duplicates")


def _index_metric_envelopes(
    results: Sequence[LensAnalysisResultInput],
) -> dict[str, LensAnalysisResultInput]:
    if results:
        identity = results[0].identity
        batch_identity = (identity.observation_id, identity.observation_run_id)
        if any(
            (result.identity.observation_id, result.identity.observation_run_id) != batch_identity
            for result in results[1:]
        ):
            raise ValueError("Lens results must share one observation_id and observation_run_id")

    metric_envelopes: dict[str, LensAnalysisResultInput] = {}
    for result in results:
        if result.result_type is not LensType.METRIC:
            continue
        lens_id = result.identity.lens_id
        if lens_id in metric_envelopes:
            raise ValueError("Metric Lens result IDs must not contain duplicates")
        metric_envelopes[lens_id] = result
    return metric_envelopes


def _resolve_current_states(
    relationships: Sequence[RelationshipCreate],
    metric_envelopes: Mapping[str, LensAnalysisResultInput],
) -> dict[str, MetricCurrentState | None]:
    participant_ids = {
        participant for relationship in relationships for participant in relationship.participants
    }
    states: dict[str, MetricCurrentState | None] = {}
    for lens_id in participant_ids:
        envelope = metric_envelopes.get(lens_id)
        if envelope is None:
            states[lens_id] = None
            continue
        result = _validate_metric_payload(envelope)
        if isinstance(result, CompletedSufficientMetricResult | PartialMetricResult):
            states[lens_id] = result.current_state
        else:
            states[lens_id] = None
    return states


def _validate_metric_payload(envelope: LensAnalysisResultInput) -> _MetricResult:
    payload = envelope.payload
    if envelope.status is LensRunStatus.FAILED:
        result_type = FailedMetricResult
    elif envelope.status is LensRunStatus.PARTIAL:
        result_type = PartialMetricResult
    elif payload.get("data_quality") == "insufficient":
        result_type = CompletedInsufficientMetricResult
    else:
        result_type = CompletedSufficientMetricResult

    try:
        return result_type.model_validate(payload)
    except ValidationError:
        try:
            serialized = json.dumps(payload)
            return result_type.model_validate_json(serialized)
        except (TypeError, ValidationError) as error:
            raise ValueError(
                f"Metric result payload for Lens {envelope.identity.lens_id!r} is invalid"
            ) from error


def _evaluate_relationship(
    relationship: RelationshipCreate,
    current_states: Mapping[str, MetricCurrentState | None],
) -> RelationshipEvaluation:
    conditions = _build_evidence(relationship, relationship.conditions, current_states)
    expectations = _build_evidence(relationship, relationship.expected, current_states)
    common = {
        "relationship_id": relationship.id,
        "name": relationship.name,
        "description": relationship.description,
        "conditions": conditions,
        "expectations": expectations,
    }
    applicability = _reduce_conditions(conditions)
    if applicability == "not_applicable":
        return NotApplicableRelationshipEvaluation(**common)
    if applicability == "unknown":
        return UnknownRelationshipEvaluation(**common)
    return ApplicableRelationshipEvaluation(
        **common,
        state=_reduce_expectations(expectations),
    )


def _build_evidence(
    relationship: RelationshipCreate,
    descriptors: Mapping[str, SemanticDescriptor],
    current_states: Mapping[str, MetricCurrentState | None],
) -> tuple[RelationshipEvidence, ...]:
    evidence: list[RelationshipEvidence] = []
    for lens_id in relationship.participants:
        descriptor = descriptors.get(lens_id)
        if descriptor is None:
            continue
        current_state = current_states.get(lens_id)
        if descriptor.trend is not None and descriptor.trend.direction is not None:
            observed = None if current_state is None else current_state.trend.direction
            expected = descriptor.trend.direction.value
            evidence.append(
                DirectionEvidence(
                    lens_id=lens_id,
                    expected=expected,
                    observed=observed,
                    match=None if observed is None else observed == expected,
                )
            )
        if descriptor.trend is not None and descriptor.trend.rate is not None:
            observed = None if current_state is None else current_state.trend.rate
            expected = descriptor.trend.rate.value
            evidence.append(
                RateEvidence(
                    lens_id=lens_id,
                    expected=expected,
                    observed=observed,
                    match=None if observed is None else observed == expected,
                )
            )
        if descriptor.variability is not None:
            observed = None if current_state is None else current_state.variability.state
            expected = descriptor.variability.state.value
            evidence.append(
                VariabilityEvidence(
                    lens_id=lens_id,
                    expected=expected,
                    observed=observed,
                    match=None if observed is None else observed == expected,
                )
            )
    return tuple(evidence)


def _reduce_conditions(evidence: Sequence[RelationshipEvidence]) -> str:
    matches = tuple(item.match for item in evidence)
    if False in matches:
        return "not_applicable"
    if None in matches:
        return "unknown"
    return "applicable"


def _reduce_expectations(evidence: Sequence[RelationshipEvidence]) -> str:
    matches = tuple(item.match for item in evidence)
    if False in matches:
        return "inconsistent"
    if None in matches:
        return "uncertain"
    return "consistent"
