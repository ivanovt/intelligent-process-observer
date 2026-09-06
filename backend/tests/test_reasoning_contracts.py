"""Strict contract tests for Observation reasoning output boundaries."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.reasoning.contracts import (
    EvidenceReference,
    FindingCompletion,
    FindingDraft,
    Hypothesis,
    ObservationAnalysisResult,
    ObservationIdentity,
)


def test_reasoning_contracts_are_immutable_and_reject_extra_fields() -> None:
    """Public reasoning artifacts remain strict framework-neutral values."""
    identity = ObservationIdentity(observation_id=uuid4(), observation_run_id=uuid4())
    reference = EvidenceReference(
        source_type="relationship_evaluation",
        source_id="relationship-1",
        locator=("state",),
    )
    result = ObservationAnalysisResult(
        identity=identity,
        overall_state="uncertain",
        findings=(),
        hypotheses=(),
        limitations=(),
    )
    assert result.model_dump()["schema_version"] == "1.0"
    with pytest.raises(ValidationError):
        FindingCompletion(
            findings=(FindingDraft(id="f", statement="x", evidence_ids=("evidence_0001",)),),
            extra="no",
        )
    with pytest.raises(ValidationError):
        reference.locator = ("other",)  # type: ignore[misc]


def test_hypothesis_requires_unique_grounding_references() -> None:
    """Hypothesis provenance cannot contain duplicate finding or knowledge links."""
    with pytest.raises(ValidationError):
        Hypothesis(
            id="h",
            statement="x",
            supported_by=("f", "f"),
            knowledge_refs=({"source_id": "s", "reference": "r"},),
        )
