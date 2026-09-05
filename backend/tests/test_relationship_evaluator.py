from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensResultIdentity,
    LensRunStatus,
    LensType,
    RelationshipEvaluationInput,
)
from app.metrics.contracts import (
    CompletedSufficientMetricResult,
    MetricCurrentAcquisitionFailed,
    MetricEvidence,
    MetricLensExecutionContext,
    MetricOptionalProjections,
    MetricProviderScope,
    MetricSample,
    MetricSemantics,
    MetricTrend,
    MetricVariability,
    PreparedGoodSeries,
)
from app.metrics.result_builder import MetricResultBuilder
from app.observations.contracts import RelationshipCreate
from app.relationships.contracts import (
    ApplicableRelationshipEvaluation,
    NotApplicableRelationshipEvaluation,
    UnknownRelationshipEvaluation,
)
from app.relationships.evaluator import RelationshipEvaluator

OBSERVATION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
RUN_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
GENERATED_AT = datetime(2026, 9, 5, 1, tzinfo=UTC)


def _relationship(
    relationship_id: str = "relationship-a",
    *,
    participants: list[str] | None = None,
    conditions: dict[str, object] | None = None,
    expected: dict[str, object] | None = None,
) -> RelationshipCreate:
    participants = participants or ["metric-a", "metric-b"]
    return RelationshipCreate(
        id=relationship_id,
        name=f"Name {relationship_id}",
        description=f"Description {relationship_id}",
        participants=participants,
        conditions=conditions or {},
        expected=expected
        or {participant: {"trend": {"direction": "increasing"}} for participant in participants},
    )


def _metric_envelope(
    lens_id: str,
    *,
    direction: str = "increasing",
    rate: str = "fast",
    variability: str = "low",
    variant: str = "completed_sufficient",
    observation_id: UUID = OBSERVATION_ID,
    observation_run_id: UUID = RUN_ID,
) -> LensAnalysisResultInput:
    context = MetricLensExecutionContext(
        identity={
            "observation_id": observation_id,
            "observation_run_id": observation_run_id,
            "lens_id": lens_id,
            "lens_run_id": uuid4(),
            "metric_ref": f"metric_{lens_id}",
            "unit": "units",
        },
        provider_scope=MetricProviderScope(
            adapter_type="prometheus",
            source_id="source-a",
            query=f"query_{lens_id}",
        ),
        analysis_window={
            "from": datetime(2026, 9, 5, tzinfo=UTC),
            "to": GENERATED_AT,
        },
        analysis_objectives=(),
        reference_periods=(),
    )
    builder = MetricResultBuilder(clock=lambda: GENERATED_AT)
    if variant == "completed_insufficient":
        return builder.completed_insufficient(context)[1]
    if variant == "failed":
        return builder.failed(
            context,
            MetricCurrentAcquisitionFailed(diagnostic="provider unavailable"),
        )[1]
    prepared = PreparedGoodSeries(
        data_quality="good",
        samples=(MetricSample(timestamp=datetime(2026, 9, 5, tzinfo=UTC), value=1.0),),
        evidence=MetricEvidence(mean=1.0, std=0.0, min=1.0, max=1.0, slope=0.0),
        residuals=(0.0,),
    )
    semantics = MetricSemantics(
        trend=MetricTrend(direction=direction, rate=rate),
        variability=MetricVariability(state=variability),
    )
    if variant == "partial":
        return builder.partial_optional_analysis_failed(
            context,
            prepared,
            semantics,
            component="metrics_agent",
            optional=MetricOptionalProjections(),
        )[1]
    assert variant == "completed_sufficient"
    return builder.completed_sufficient(context, prepared, semantics)[1]


def _alert_envelope(
    lens_id: str,
    *,
    observation_id: UUID = OBSERVATION_ID,
    observation_run_id: UUID = RUN_ID,
) -> LensAnalysisResultInput:
    identity = LensResultIdentity(
        observation_id=observation_id,
        observation_run_id=observation_run_id,
        lens_id=lens_id,
        lens_run_id=uuid4(),
    )
    provenance = {"source": "test", "generated_at": "2026-09-05T01:00:00Z"}
    return LensAnalysisResultInput(
        result_type=LensType.ALERT,
        status=LensRunStatus.COMPLETED,
        schema_version="1.0",
        identity=identity,
        provenance=provenance,
        payload={
            "schema_version": "1.0",
            "lens_type": "alert",
            "status": "completed",
            "identity": identity.model_dump(mode="json"),
            "provenance": provenance,
        },
    )


def test_complete_collection_ignores_non_metric_same_id_and_unrelated_metrics() -> None:
    relationship = _relationship(
        conditions={"metric-b": {"trend": {"direction": "increasing"}}},
        expected={"metric-a": {"trend": {"direction": "increasing"}}},
    )

    evaluation = RelationshipEvaluator().evaluate(
        (relationship,),
        (
            _alert_envelope("metric-a"),
            _metric_envelope("metric-b"),
            _metric_envelope("unrelated"),
        ),
    )[0]

    assert isinstance(evaluation, ApplicableRelationshipEvaluation)
    assert evaluation.state == "uncertain"
    assert evaluation.expectations[0].observed is None
    assert evaluation.expectations[0].match is None


@pytest.mark.parametrize("identity_field", ["observation_id", "observation_run_id"])
def test_complete_collection_rejects_disagreement_in_each_batch_identity_field(
    identity_field: str,
) -> None:
    override = {
        identity_field: UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
    }
    first = _metric_envelope("metric-a")
    second = _metric_envelope("metric-b", **override)

    with pytest.raises(ValueError, match="must share"):
        RelationshipEvaluator().evaluate((_relationship(),), (first, second))


def test_complete_collection_rejects_duplicate_metric_lens_ids() -> None:
    results = (_metric_envelope("metric-a"), _metric_envelope("metric-a"))

    with pytest.raises(ValueError, match="Metric Lens result IDs"):
        RelationshipEvaluator().evaluate((_relationship(),), results)


def test_matching_malformed_metric_payload_rejects_batch_but_unrelated_one_is_ignored() -> None:
    valid = _metric_envelope("metric-a")
    malformed_payload = valid.payload | {
        "current_state": valid.payload["current_state"] | {"variability": {}},
    }
    malformed = LensAnalysisResultInput.model_validate(
        valid.model_dump() | {"payload": malformed_payload}
    )

    with pytest.raises(ValueError, match="payload.*invalid"):
        RelationshipEvaluator().evaluate(
            (_relationship(),),
            (malformed, _metric_envelope("metric-b")),
        )

    evaluation = RelationshipEvaluator().evaluate(
        (_relationship(participants=["metric-b", "metric-c"]),),
        (malformed, _metric_envelope("metric-b"), _metric_envelope("metric-c")),
    )[0]
    assert isinstance(evaluation, ApplicableRelationshipEvaluation)
    assert evaluation.state == "consistent"


def test_matching_python_shaped_strict_metric_payload_is_accepted() -> None:
    serialized = _metric_envelope("metric-a")
    result = CompletedSufficientMetricResult.model_validate_json(json.dumps(serialized.payload))
    payload = result.model_dump(by_alias=True)
    python_shaped = LensAnalysisResultInput.model_validate(
        serialized.model_dump() | {"provenance": payload["provenance"], "payload": payload}
    )

    evaluation = RelationshipEvaluator().evaluate(
        (_relationship(),),
        (python_shaped, _metric_envelope("metric-b")),
    )[0]

    assert isinstance(evaluation, ApplicableRelationshipEvaluation)
    assert evaluation.state == "consistent"


@pytest.mark.parametrize("variant", ["completed_insufficient", "failed", "missing"])
def test_missing_or_valid_non_usable_participant_is_unavailable_without_aborting(
    variant: str,
) -> None:
    results = () if variant == "missing" else (_metric_envelope("metric-a", variant=variant),)
    results += (_metric_envelope("metric-b"),)

    evaluation = RelationshipEvaluator().evaluate(
        (
            _relationship(
                conditions={"metric-b": {"trend": {"direction": "increasing"}}},
                expected={"metric-a": {"trend": {"direction": "increasing"}}},
            ),
        ),
        results,
    )[0]

    assert isinstance(evaluation, ApplicableRelationshipEvaluation)
    assert evaluation.state == "uncertain"
    assert evaluation.expectations[0].observed is None


def test_partial_metric_result_exposes_current_state() -> None:
    evaluation = RelationshipEvaluator().evaluate(
        (_relationship(),),
        (
            _metric_envelope("metric-a", variant="partial"),
            _metric_envelope("metric-b"),
        ),
    )[0]

    assert isinstance(evaluation, ApplicableRelationshipEvaluation)
    assert evaluation.state == "consistent"


def test_duplicate_relationship_ids_are_rejected_atomically_without_mutation() -> None:
    first = _relationship("duplicate")
    second = first.model_copy(update={"name": "Second valid definition"})
    result = _metric_envelope("metric-a")
    before_relationships = [item.model_dump(mode="json") for item in (first, second)]
    before_results = [result.model_dump(mode="json")]

    with pytest.raises(ValueError, match="relationship IDs"):
        RelationshipEvaluator().evaluate((first, second), (result,))

    assert [item.model_dump(mode="json") for item in (first, second)] == before_relationships
    assert [result.model_dump(mode="json")] == before_results


def test_evidence_is_complete_and_canonical_independent_of_mapping_order() -> None:
    relationship = _relationship(
        participants=["metric-b", "metric-a"],
        conditions={
            "metric-a": {"trend": {"rate": "slow"}},
            "metric-b": {
                "variability": {"state": "high"},
                "trend": {"rate": "fast", "direction": "increasing"},
            },
        },
        expected={
            "metric-a": {"variability": {"state": "low"}},
            "metric-b": {"trend": {"direction": "decreasing"}},
        },
    )

    evaluation = RelationshipEvaluator().evaluate(
        (relationship,),
        (
            _metric_envelope("metric-a", direction="decreasing", rate="slow"),
            _metric_envelope("metric-b", direction="increasing", rate="fast"),
        ),
    )[0]

    assert [
        (item.lens_id, item.property, item.expected, item.observed, item.match)
        for item in evaluation.conditions
    ] == [
        ("metric-b", "trend.direction", "increasing", "increasing", True),
        ("metric-b", "trend.rate", "fast", "fast", True),
        ("metric-b", "variability.state", "high", "low", False),
        ("metric-a", "trend.rate", "slow", "slow", True),
    ]
    assert [item.property for item in evaluation.expectations] == [
        "trend.direction",
        "variability.state",
    ]


def test_not_classified_rate_is_reliable_mismatch() -> None:
    relationship = _relationship(
        conditions={"metric-b": {"trend": {"direction": "increasing"}}},
        expected={"metric-a": {"trend": {"rate": "fast"}}},
    )

    evaluation = RelationshipEvaluator().evaluate(
        (relationship,),
        (
            _metric_envelope("metric-a", direction="stable", rate="not_classified"),
            _metric_envelope("metric-b"),
        ),
    )[0]

    assert isinstance(evaluation, ApplicableRelationshipEvaluation)
    assert evaluation.state == "inconsistent"
    assert evaluation.expectations[0].observed == "not_classified"
    assert evaluation.expectations[0].match is False


@pytest.mark.parametrize(
    ("conditions", "expected", "result_lenses", "evaluation_type", "state"),
    [
        (
            {},
            {
                "metric-a": {"trend": {"direction": "increasing"}},
                "metric-b": {"trend": {"direction": "increasing"}},
            },
            ("metric-a", "metric-b"),
            ApplicableRelationshipEvaluation,
            "consistent",
        ),
        (
            {"metric-a": {"trend": {"direction": "increasing"}}},
            {"metric-b": {"trend": {"direction": "decreasing"}}},
            ("metric-a", "metric-b"),
            ApplicableRelationshipEvaluation,
            "inconsistent",
        ),
        (
            {"metric-a": {"trend": {"direction": "increasing"}}},
            {"metric-b": {"trend": {"direction": "increasing"}}},
            ("metric-a",),
            ApplicableRelationshipEvaluation,
            "uncertain",
        ),
        (
            {"metric-a": {"trend": {"direction": "decreasing"}}},
            {"metric-b": {"trend": {"direction": "increasing"}}},
            ("metric-a", "metric-b"),
            NotApplicableRelationshipEvaluation,
            None,
        ),
        (
            {"metric-a": {"trend": {"direction": "increasing"}}},
            {"metric-b": {"trend": {"direction": "increasing"}}},
            ("metric-b",),
            UnknownRelationshipEvaluation,
            None,
        ),
    ],
)
def test_semantic_matrix(
    conditions: dict[str, object],
    expected: dict[str, object],
    result_lenses: tuple[str, ...],
    evaluation_type: type,
    state: str | None,
) -> None:
    participants = list(dict.fromkeys((*conditions, *expected)))
    relationship = _relationship(
        participants=participants,
        conditions=conditions,
        expected=expected,
    )
    results = tuple(
        _metric_envelope(
            lens_id,
            direction="increasing" if lens_id == "metric-a" else "increasing",
        )
        for lens_id in result_lenses
    )

    evaluation = RelationshipEvaluator().evaluate((relationship,), results)[0]

    assert isinstance(evaluation, evaluation_type)
    assert getattr(evaluation, "state", None) == state
    assert len(evaluation.conditions) == sum(
        int(descriptor.trend is not None and descriptor.trend.direction is not None)
        for descriptor in relationship.conditions.values()
    )
    assert len(evaluation.expectations) == sum(
        int(descriptor.trend is not None and descriptor.trend.direction is not None)
        for descriptor in relationship.expected.values()
    )


def test_mismatch_dominates_unavailable_condition_and_expectation_evidence() -> None:
    condition_rule = _relationship(
        conditions={
            "metric-a": {"trend": {"direction": "decreasing"}},
            "metric-b": {"trend": {"direction": "increasing"}},
        },
        expected={"metric-a": {"variability": {"state": "low"}}},
    )
    condition_evaluation = RelationshipEvaluator().evaluate(
        (condition_rule,),
        (_metric_envelope("metric-a"),),
    )[0]
    assert isinstance(condition_evaluation, NotApplicableRelationshipEvaluation)
    assert [item.match for item in condition_evaluation.conditions] == [False, None]
    assert len(condition_evaluation.expectations) == 1

    expectation_rule = _relationship(
        conditions={},
        expected={
            "metric-a": {"trend": {"direction": "decreasing"}},
            "metric-b": {"trend": {"direction": "increasing"}},
        },
    )
    expectation_evaluation = RelationshipEvaluator().evaluate(
        (expectation_rule,),
        (_metric_envelope("metric-a"),),
    )[0]
    assert isinstance(expectation_evaluation, ApplicableRelationshipEvaluation)
    assert expectation_evaluation.state == "inconsistent"
    assert [item.match for item in expectation_evaluation.expectations] == [False, None]


def test_unknown_evaluation_keeps_complete_expectation_evidence() -> None:
    relationship = _relationship(
        conditions={"metric-a": {"trend": {"direction": "increasing"}}},
        expected={"metric-b": {"variability": {"state": "low"}}},
    )

    evaluation = RelationshipEvaluator().evaluate(
        (relationship,),
        (_metric_envelope("metric-b"),),
    )[0]

    assert isinstance(evaluation, UnknownRelationshipEvaluation)
    assert len(evaluation.conditions) == 1
    assert evaluation.conditions[0].match is None
    assert len(evaluation.expectations) == 1
    assert evaluation.expectations[0].match is True


def test_ordered_batch_empty_batch_all_unavailable_and_successful_input_immutability() -> None:
    relationships = (_relationship("relationship-b"), _relationship("relationship-a"))
    results = (
        _metric_envelope("metric-a", variant="completed_insufficient"),
        _metric_envelope("metric-b", variant="failed"),
    )
    before = [relationship.model_dump(mode="json") for relationship in relationships]
    before_results = [result.model_dump(mode="json") for result in results]

    evaluations = RelationshipEvaluator().evaluate(relationships, results)

    assert [item.relationship_id for item in evaluations] == ["relationship-b", "relationship-a"]
    assert all(
        isinstance(item, ApplicableRelationshipEvaluation) and item.state == "uncertain"
        for item in evaluations
    )
    assert [relationship.model_dump(mode="json") for relationship in relationships] == before
    assert [result.model_dump(mode="json") for result in results] == before_results
    assert RelationshipEvaluator().evaluate((), results) == ()


def test_all_evaluation_variants_fit_generic_persistence_input_without_persistence_calls() -> None:
    relationships = (
        _relationship("applicable"),
        _relationship(
            "not-applicable",
            conditions={"metric-a": {"trend": {"direction": "decreasing"}}},
            expected={"metric-b": {"trend": {"direction": "increasing"}}},
        ),
        _relationship(
            "unknown",
            participants=["metric-c", "metric-d"],
            conditions={"metric-c": {"trend": {"direction": "increasing"}}},
            expected={"metric-d": {"trend": {"direction": "increasing"}}},
        ),
    )
    evaluations = RelationshipEvaluator().evaluate(
        relationships,
        (_metric_envelope("metric-a"), _metric_envelope("metric-b")),
    )

    inputs = tuple(
        RelationshipEvaluationInput(
            relationship_id=evaluation.relationship_id,
            payload=evaluation.model_dump(mode="json"),
        )
        for evaluation in evaluations
    )

    assert [item.payload["applicability"] for item in inputs] == [
        "applicable",
        "not_applicable",
        "unknown",
    ]
    assert "state" in inputs[0].payload
    assert "state" not in inputs[1].payload
    assert "state" not in inputs[2].payload
