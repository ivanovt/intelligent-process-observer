"""Strict contract tests for Observation reasoning output boundaries."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.infrastructure.persistence.runtime_contracts import (
    ObservationAnalysisIdentity,
    ObservationAnalysisResultInput,
)
from app.knowledge.contracts import KnowledgeReference
from app.reasoning.builder import build_result, freeze_findings, validate_hypotheses
from app.reasoning.catalog import build_catalog
from app.reasoning.contracts import (
    EvidenceReference,
    FindingCompletion,
    FindingDraft,
    Hypothesis,
    HypothesisCompletion,
    ObservationAnalysisResult,
    ObservationIdentity,
    OverallStateCompletion,
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


def test_freeze_rejects_unknown_or_duplicate_catalog_references() -> None:
    """Finding drafts can only cite unique transient catalog entries."""
    with pytest.raises(ValueError):
        freeze_findings(
            FindingCompletion(
                findings=(FindingDraft(id="f", statement="x", evidence_ids=("missing",)),)
            ),
            (),
        )


def _catalog_for_all_reasoning_sources():
    """Build a deterministic catalog spanning every source kind admitted by reasoning."""
    metric_id, alert_id = uuid4(), uuid4()
    metric = SimpleNamespace(
        lens_type="metric",
        identity=SimpleNamespace(lens_run_id=metric_id),
        model_dump=lambda mode: {"current_state": {"trend": {"direction": "increasing"}}},
    )
    alert = SimpleNamespace(
        lens_type="alert",
        identity=SimpleNamespace(lens_run_id=alert_id),
        model_dump=lambda mode: {"alerts": [{"id": "alert-1", "title": "High temperature"}]},
    )
    relationship = SimpleNamespace(
        relationship_id="relationship-1",
        model_dump=lambda mode: {"applicability": "applicable", "state": "inconsistent"},
    )
    return build_catalog(
        SimpleNamespace(usable_results=(metric, alert), relationships=(relationship,))
    )


def test_builder_freezes_zero_and_multiple_cross_lens_findings_without_catalog_ids() -> None:
    """Freezing preserves authored order while replacing run-local IDs across Lens sources."""
    catalog = _catalog_for_all_reasoning_sources()
    metric, alert, relationship = (
        next(entry for entry in catalog if entry.reference.source_type == source_type)
        for source_type in ("metric_result", "alert_result", "relationship_evaluation")
    )

    assert freeze_findings(FindingCompletion(), catalog) == ()
    frozen = freeze_findings(
        FindingCompletion(
            findings=(
                FindingDraft(
                    id="f-1",
                    statement="The metric and alert changed together.",
                    evidence_ids=(metric.id, alert.id),
                ),
                FindingDraft(
                    id="f-2",
                    statement="The relationship is inconsistent.",
                    evidence_ids=(relationship.id,),
                ),
            )
        ),
        catalog,
    )

    assert [finding.id for finding in frozen] == ["f-1", "f-2"]
    assert frozen[0].evidence_refs == (metric.reference, alert.reference)
    assert frozen[1].evidence_refs == (relationship.reference,)
    assert "evidence_ids" not in frozen[0].model_dump()
    assert "evidence_000" not in frozen[0].model_dump_json()


def test_builder_preserves_snapshots_and_accepts_uncertain_with_findings_and_hypotheses() -> None:
    """Final construction copies frozen evidence, plural hypotheses, and uncertainty unchanged."""
    catalog = _catalog_for_all_reasoning_sources()
    findings = freeze_findings(
        FindingCompletion(
            findings=(
                FindingDraft(id="f-1", statement="Metric changed.", evidence_ids=(catalog[0].id,)),
                FindingDraft(
                    id="f-2", statement="Alert is present.", evidence_ids=(catalog[1].id,)
                ),
            )
        ),
        catalog,
    )
    first_reference = KnowledgeReference(source_id="kb-a", reference="document#one")
    second_reference = KnowledgeReference(source_id="kb-b", reference="document#two")
    hypotheses = validate_hypotheses(
        HypothesisCompletion(
            hypotheses=(
                Hypothesis(
                    id="h-1",
                    statement="A possible explanation is documented.",
                    supported_by=("f-1",),
                    knowledge_refs=(first_reference,),
                ),
                Hypothesis(
                    id="h-2",
                    statement="A second explanation remains possible.",
                    supported_by=("f-1", "f-2"),
                    knowledge_refs=(second_reference,),
                ),
            )
        ),
        findings,
        (first_reference, second_reference),
    )
    identity = ObservationIdentity(observation_id=uuid4(), observation_run_id=uuid4())
    value = SimpleNamespace(context=SimpleNamespace(identity=identity))
    limitations = ()

    result = build_result(
        value,
        findings,
        hypotheses,
        OverallStateCompletion(overall_state="uncertain"),
        limitations,
    )

    assert result.findings == findings
    assert result.hypotheses == hypotheses
    assert result.limitations == limitations
    assert result.overall_state == "uncertain"
    envelope = ObservationAnalysisResultInput(
        schema_version=result.schema_version,
        identity=ObservationAnalysisIdentity(**identity.model_dump()),
        payload=result.model_dump(mode="json"),
    )
    assert envelope.payload == result.model_dump(mode="json")


@pytest.mark.parametrize(
    ("operation", "message"),
    (
        (
            lambda: freeze_findings(
                FindingCompletion(
                    findings=(FindingDraft(id="f", statement="x", evidence_ids=("unknown",)),)
                ),
                (),
            ),
            "catalog",
        ),
        (
            lambda: validate_hypotheses(
                HypothesisCompletion(
                    hypotheses=(
                        Hypothesis(
                            id="h",
                            statement="x",
                            supported_by=("unknown",),
                            knowledge_refs=(KnowledgeReference(source_id="s", reference="r"),),
                        ),
                    )
                ),
                (),
                (KnowledgeReference(source_id="s", reference="r"),),
            ),
            "grounding",
        ),
        (
            lambda: validate_hypotheses(
                HypothesisCompletion(
                    hypotheses=(
                        Hypothesis(
                            id="h",
                            statement="x",
                            supported_by=("f",),
                            knowledge_refs=(
                                KnowledgeReference(source_id="unknown", reference="r"),
                            ),
                        ),
                    )
                ),
                freeze_findings(
                    FindingCompletion(
                        findings=(
                            FindingDraft(id="f", statement="x", evidence_ids=("evidence_0001",)),
                        )
                    ),
                    (
                        SimpleNamespace(
                            id="evidence_0001",
                            reference=EvidenceReference(
                                source_type="relationship_evaluation",
                                source_id="r",
                                locator=("state",),
                            ),
                        ),
                    ),
                ),
                (),
            ),
            "grounding",
        ),
    ),
)
def test_builder_rejects_unknown_evidence_finding_and_knowledge(operation, message: str) -> None:
    """Every final traceability link must have been supplied during this run."""
    with pytest.raises(ValueError, match=message):
        operation()


def test_reasoning_serialization_forbids_taxonomy_confidence_and_recommendations() -> None:
    """Structured outputs cannot acquire unsupported interpretation or action fields."""
    for model, payload in (
        (
            FindingDraft,
            {"id": "f", "statement": "x", "evidence_ids": ("evidence_0001",), "severity": "high"},
        ),
        (
            Hypothesis,
            {
                "id": "h",
                "statement": "x",
                "supported_by": ("f",),
                "knowledge_refs": ({"source_id": "s", "reference": "r"},),
                "confidence": 0.9,
            },
        ),
        (
            ObservationAnalysisResult,
            {
                "identity": ObservationIdentity(observation_id=uuid4(), observation_run_id=uuid4()),
                "overall_state": "uncertain",
                "findings": (),
                "hypotheses": (),
                "limitations": (),
                "recommendation": "restart",
            },
        ),
    ):
        with pytest.raises(ValidationError, match="Extra inputs"):
            model.model_validate(payload)
