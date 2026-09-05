from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from app.relationships.contracts import (
    ApplicableRelationshipEvaluation,
    DirectionEvidence,
    NotApplicableRelationshipEvaluation,
    RateEvidence,
    RelationshipEvaluation,
    UnknownRelationshipEvaluation,
    VariabilityEvidence,
)


def test_evaluation_variants_serialize_exact_complete_contracts() -> None:
    condition = DirectionEvidence(
        lens_id="pump-speed",
        expected="increasing",
        observed="increasing",
        match=True,
    )
    expectation = RateEvidence(
        lens_id="flow",
        expected="fast",
        observed="not_classified",
        match=False,
    )

    applicable = ApplicableRelationshipEvaluation(
        relationship_id="pump-flow",
        name="Pump flow",
        description=None,
        applicability="applicable",
        state="inconsistent",
        conditions=(condition,),
        expectations=(expectation,),
    )
    not_applicable = NotApplicableRelationshipEvaluation(
        relationship_id="pump-flow",
        name="Pump flow",
        description=None,
        conditions=(condition,),
        expectations=(expectation,),
    )
    unknown = UnknownRelationshipEvaluation(
        relationship_id="pump-flow",
        name="Pump flow",
        description=None,
        conditions=(condition,),
        expectations=(expectation,),
    )

    assert applicable.model_dump(mode="json") == {
        "relationship_id": "pump-flow",
        "name": "Pump flow",
        "description": None,
        "conditions": [condition.model_dump(mode="json")],
        "expectations": [expectation.model_dump(mode="json")],
        "applicability": "applicable",
        "state": "inconsistent",
    }
    assert "state" not in not_applicable.model_dump(mode="json")
    assert "state" not in unknown.model_dump(mode="json")
    assert "schema_version" not in applicable.model_dump(mode="json")


@pytest.mark.parametrize(
    ("evidence_type", "payload"),
    [
        (
            DirectionEvidence,
            {
                "lens_id": "metric-a",
                "property": "trend.direction",
                "expected": "increasing",
                "observed": "unknown",
                "match": False,
            },
        ),
        (
            RateEvidence,
            {
                "lens_id": "metric-a",
                "property": "trend.rate",
                "expected": "fast",
                "observed": "unexpected",
                "match": False,
            },
        ),
        (
            VariabilityEvidence,
            {
                "lens_id": "metric-a",
                "property": "variability.state",
                "expected": "low",
                "observed": "not_classified",
                "match": False,
            },
        ),
    ],
)
def test_evidence_rejects_values_outside_property_vocabulary(
    evidence_type: type[DirectionEvidence] | type[RateEvidence] | type[VariabilityEvidence],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        evidence_type.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"observed": None, "match": True},
        {"observed": "stable", "match": None},
        {"observed": "stable", "match": False},
        {"observed": "increasing", "match": True},
    ],
)
def test_evidence_rejects_contradictory_match_values(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DirectionEvidence(
            lens_id="metric-a",
            expected="stable",
            **payload,
        )


def test_unavailable_evidence_requires_explicit_nulls() -> None:
    evidence = VariabilityEvidence(
        lens_id="metric-a",
        expected="high",
        observed=None,
        match=None,
    )

    assert evidence.model_dump(mode="json") == {
        "lens_id": "metric-a",
        "property": "variability.state",
        "expected": "high",
        "observed": None,
        "match": None,
    }


def test_evaluation_union_rejects_illegal_state_combinations_and_extra_fields() -> None:
    adapter = TypeAdapter(RelationshipEvaluation)
    base = {
        "relationship_id": "pump-flow",
        "name": "Pump flow",
        "description": None,
        "conditions": [],
        "expectations": [],
    }

    for payload in (
        base | {"applicability": "applicable"},
        base | {"applicability": "not_applicable", "state": "consistent"},
        base | {"applicability": "unknown", "state": "uncertain"},
        base | {"applicability": "unknown", "extra": "forbidden"},
    ):
        with pytest.raises(ValidationError):
            adapter.validate_json(json.dumps(payload))
