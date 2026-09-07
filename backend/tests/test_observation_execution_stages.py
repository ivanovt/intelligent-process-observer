from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.execution.contracts import (
    AnalysisWindow,
    ObservationExecutionSnapshot,
    RelationshipSnapshot,
    SemanticDescriptorSnapshot,
)
from app.execution.projectors import (
    relationship_definitions,
    validate_relationship_batch,
)


def _snapshot() -> ObservationExecutionSnapshot:
    return ObservationExecutionSnapshot(
        observation_id=uuid4(),
        schema_version=1,
        analysis_window=AnalysisWindow(
            from_=datetime(2026, 1, 1, tzinfo=UTC),
            to=datetime(2026, 1, 2, tzinfo=UTC),
        ),
        name="Observation",
        description=None,
        objective="detect drift",
        metric_lenses=(),
        alert_lenses=(),
        relationships=(
            RelationshipSnapshot(
                relationship_id="first",
                name="First",
                description=None,
                participants=("m1", "m2"),
                conditions=(("m1", SemanticDescriptorSnapshot("increasing", None, None)),),
                expected=(("m2", SemanticDescriptorSnapshot(None, None, "high")),),
            ),
        ),
    )


def test_relationship_projection_preserves_definition_order_and_semantics() -> None:
    relationship = relationship_definitions(_snapshot())[0]

    assert relationship.id == "first"
    assert relationship.participants == ["m1", "m2"]
    assert relationship.conditions["m1"].trend.direction == "increasing"
    assert relationship.expected["m2"].variability.state == "high"


def test_relationship_batch_rejects_missing_duplicate_or_reordered_identity() -> None:
    snapshot = _snapshot()
    observation_id = snapshot.observation_id
    run_id = uuid4()

    with pytest.raises(ValueError, match="cardinality"):
        validate_relationship_batch(
            snapshot, (), observation_id=observation_id, observation_run_id=run_id
        )

    class Evaluation:
        relationship_id = "other"

    with pytest.raises(ValueError, match="identity or order"):
        validate_relationship_batch(
            snapshot,
            (Evaluation(),),
            observation_id=observation_id,
            observation_run_id=run_id,
        )
