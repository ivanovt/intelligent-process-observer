"""Focused regression tests for Observation reasoning evidence projection."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.reasoning.catalog import build_catalog, resolve_reference
from app.reasoning.contracts import (
    EvidenceReference,
    ObservationIdentity,
    ObservationReasoningInput,
    ObservationSemanticContext,
    ReasoningLens,
    UnavailableLens,
)
from app.reasoning.input import derive_limitations


def test_alert_catalog_projects_each_record_as_one_concrete_element() -> None:
    """Alert records are referenced as complete immutable source elements."""
    lens_run_id = uuid4()
    alert = SimpleNamespace(
        lens_type="alert",
        identity=SimpleNamespace(lens_run_id=lens_run_id),
        model_dump=lambda mode: {
            "alerts": [
                {
                    "id": "alert-1",
                    "source_ref": "provider://private",
                    "status": {"normalized": "active", "source": "provider-status"},
                }
            ],
            "alert_activity": {"record_count": 1},
            "status_distribution": {"active": 1},
            "overall_importance": "high",
        },
    )
    value = SimpleNamespace(usable_results=(alert,), relationships=())

    catalog = build_catalog(value)

    locators = {entry.reference.locator for entry in catalog}
    assert locators == {
        ("alerts", 0),
        ("alert_activity", "record_count"),
        ("status_distribution", "active"),
        ("overall_importance",),
    }


def _source(*, lens_type: str, source_id: object, payload: dict[str, object]):
    return SimpleNamespace(
        lens_type=lens_type,
        identity=SimpleNamespace(lens_run_id=source_id),
        model_dump=lambda mode: payload,
    )


def test_catalog_projects_three_source_types_in_supplied_order_with_transient_ids() -> None:
    """Catalog IDs are run-local ordinals over the fixed admitted source order."""
    metric_id, alert_id = uuid4(), uuid4()
    metric = _source(
        lens_type="metric",
        source_id=metric_id,
        payload={
            "identity": {"private": "excluded"},
            "current_state": {"trend": {"direction": "stable"}},
            "reference_periods": [{"offset": "1h", "direction": "increased"}],
            "history": {"run_ids": ["old-run"]},
            "evidence": {"current": {"mean": 4.0}, "history": {"runs": 1}},
            "provenance": {"source": "excluded"},
        },
    )
    alert = _source(
        lens_type="alert",
        source_id=alert_id,
        payload={
            "alerts": [{"id": "a-1", "title": "High temperature"}],
            "alert_activity": {"record_count": 1},
            "status_distribution": {"active": 1},
            "comparisons": [{"offset": "1h", "delta": 1}],
            "findings": [{"id": "local", "statement": "present"}],
            "overall_importance": "high",
            "provenance": {"source_provider": "excluded"},
        },
    )
    relationship = SimpleNamespace(
        relationship_id="relationship-1",
        model_dump=lambda mode: {
            "applicability": "applicable",
            "state": "consistent",
            "conditions": [{"lens_id": "metric", "match": True}],
            "expectations": [{"lens_id": "alert", "match": False}],
            "name": "excluded",
        },
    )
    value = SimpleNamespace(usable_results=(metric, alert), relationships=(relationship,))

    catalog = build_catalog(value)

    assert [entry.id for entry in catalog] == [
        f"evidence_{number:04d}" for number in range(1, len(catalog) + 1)
    ]
    assert [entry.reference.source_type for entry in catalog] == sorted(
        (entry.reference.source_type for entry in catalog),
        key={"metric_result": 0, "alert_result": 1, "relationship_evaluation": 2}.get,
    )
    assert catalog[0].reference == EvidenceReference(
        source_type="metric_result",
        source_id=metric_id,
        locator=("current_state", "trend", "direction"),
    )
    assert any(
        entry.reference.source_type == "alert_result" and entry.reference.locator == ("alerts", 0)
        for entry in catalog
    )
    assert any(
        entry.reference.source_type == "relationship_evaluation"
        and entry.reference.locator == ("conditions", 0)
        for entry in catalog
    )
    assert all(
        not ({"identity", "provenance", "name"} & set(entry.reference.locator)) for entry in catalog
    )


def test_catalog_keeps_compound_evidence_items_whole_and_omits_analysis_windows() -> None:
    """Catalog granularity is source-specific rather than generic leaf traversal."""
    metric = _source(
        lens_type="metric",
        source_id="metric-run",
        payload={
            "analysis_window": {"start": "excluded", "end": "excluded"},
            "current_state": {"trend": "stable"},
            "reference_periods": [
                {
                    "offset": "1h",
                    "analysis_window": {"start": "excluded"},
                    "level": {"relation": "higher"},
                }
            ],
            "history": {"direction": "stable", "run_ids": ["run-1"]},
            "evidence": {
                "current": {"mean": 2.0},
                "reference_periods": [
                    {"offset": "1h", "analysis_window": {"start": "excluded"}, "mean": 1.0}
                ],
                "history": {"direction_changes": 0},
            },
        },
    )
    alert = _source(
        lens_type="alert",
        source_id="alert-run",
        payload={
            "alerts": [{"id": "a-1", "title": "High temperature"}],
            "comparisons": [{"offset": "1h", "occurrence_comparison": {"delta": 1}}],
            "findings": [{"id": "local", "statement": "present"}],
            "overall_importance": "high",
        },
    )
    relationship = SimpleNamespace(
        relationship_id="relationship-1",
        model_dump=lambda mode: {
            "applicability": "applicable",
            "state": "consistent",
            "conditions": [{"lens_id": "metric", "match": True}],
            "expectations": [{"lens_id": "metric", "match": False}],
        },
    )

    catalog = build_catalog(
        SimpleNamespace(usable_results=(metric, alert), relationships=(relationship,))
    )
    locators_by_source = {
        source_type: [
            entry.reference.locator
            for entry in catalog
            if entry.reference.source_type == source_type
        ]
        for source_type in ("metric_result", "alert_result", "relationship_evaluation")
    }

    assert locators_by_source["metric_result"] == [
        ("current_state", "trend"),
        ("reference_periods", 0),
        ("evidence", "current", "mean"),
        ("evidence", "reference_periods", 0),
        ("history", "direction"),
        ("history", "run_ids", 0),
        ("evidence", "history", "direction_changes"),
    ]
    assert locators_by_source["alert_result"] == [
        ("alerts", 0),
        ("comparisons", 0),
        ("findings", 0),
        ("overall_importance",),
    ]
    assert locators_by_source["relationship_evaluation"] == [
        ("applicability",),
        ("state",),
        ("conditions", 0),
        ("expectations", 0),
    ]


def test_catalog_omits_absent_optional_sections_and_ids_translate_per_run() -> None:
    """Absent optional evidence contributes no catalog entries and IDs are transient."""
    source_id = uuid4()
    result = _source(
        lens_type="metric",
        source_id=source_id,
        payload={
            "current_state": {"trend": "stable"},
            "reference_periods": None,
            "history": None,
            "evidence": {"current": {"mean": 1.0}, "reference_periods": None, "history": None},
        },
    )
    first = build_catalog(SimpleNamespace(usable_results=(result,), relationships=()))
    second = build_catalog(SimpleNamespace(usable_results=(result,), relationships=()))

    assert first == second
    assert [entry.reference.locator for entry in first] == [
        ("current_state", "trend"),
        ("evidence", "current", "mean"),
    ]
    assert (
        resolve_reference(
            first[0].reference, SimpleNamespace(usable_results=(result,), relationships=())
        )
        == "stable"
    )


@pytest.mark.parametrize(
    ("reference", "message"),
    (
        (
            EvidenceReference(source_type="metric_result", source_id="missing", locator=("x",)),
            "exactly one source",
        ),
        (
            EvidenceReference(source_type="metric_result", source_id="same", locator=("missing",)),
            "locator is invalid",
        ),
        (
            EvidenceReference(source_type="metric_result", source_id="same", locator=("value", 0)),
            "locator is invalid",
        ),
        (
            EvidenceReference(source_type="metric_result", source_id="same", locator=("items", 2)),
            "locator is invalid",
        ),
    ),
)
def test_resolver_rejects_missing_malformed_and_scalar_locators(
    reference: EvidenceReference, message: str
) -> None:
    """Resolution cannot escape or guess a validated source artifact."""
    source = _source(
        lens_type="metric", source_id="same", payload={"value": "scalar", "items": ["one"]}
    )
    with pytest.raises(ValueError, match=message):
        resolve_reference(reference, SimpleNamespace(usable_results=(source,), relationships=()))


def test_resolver_rejects_ambiguous_sources_and_resolves_relationship_exactly() -> None:
    """Source IDs must identify exactly one artifact across the admitted type."""
    duplicate = tuple(
        _source(lens_type="alert", source_id="same", payload={"overall_importance": "low"})
        for _ in range(2)
    )
    with pytest.raises(ValueError, match="exactly one source"):
        resolve_reference(
            EvidenceReference(
                source_type="alert_result", source_id="same", locator=("overall_importance",)
            ),
            SimpleNamespace(usable_results=duplicate, relationships=()),
        )
    relationship = SimpleNamespace(
        relationship_id="r", model_dump=lambda mode: {"applicability": "unknown"}
    )
    assert (
        resolve_reference(
            EvidenceReference(
                source_type="relationship_evaluation", source_id="r", locator=("applicability",)
            ),
            SimpleNamespace(usable_results=(), relationships=(relationship,)),
        )
        == "unknown"
    )


def test_limitations_map_order_empty_and_immutability(monkeypatch: pytest.MonkeyPatch) -> None:
    """Availability limitations are immutable, complete, and follow semantic Lens order."""
    import app.reasoning.input as reasoning_input

    partial = SimpleNamespace(
        identity=SimpleNamespace(lens_id="partial"), reason=SimpleNamespace(component="history")
    )
    monkeypatch.setattr(reasoning_input, "PartialMetricResult", type(partial))
    monkeypatch.setattr(
        reasoning_input, "PartialAlertAnalysisResult", type("NoAlertPartial", (), {})
    )
    identity = ObservationIdentity(observation_id=uuid4(), observation_run_id=uuid4())
    value = ObservationReasoningInput.model_construct(
        context=ObservationSemanticContext(
            identity=identity,
            name="Observation",
            lenses=(
                ReasoningLens(lens_id="missing", lens_type="alert"),
                ReasoningLens(lens_id="partial", lens_type="metric"),
                ReasoningLens(lens_id="insufficient", lens_type="metric"),
            ),
        ),
        usable_results=(partial,),
        unavailable_lenses=(
            UnavailableLens(
                lens_id="insufficient", lens_type="metric", reason={"code": "insufficient_data"}
            ),
            UnavailableLens(
                lens_id="missing", lens_type="alert", reason={"code": "upstream_failed"}
            ),
        ),
        relationships=(),
    )

    limitations = derive_limitations(value)

    actual_limitations = [
        (item.code, item.lens_id, getattr(item, "component", None)) for item in limitations
    ]
    assert actual_limitations == [
        ("missing_lens_evidence", "missing", None),
        ("partial_lens_analysis", "partial", "history"),
        ("insufficient_lens_evidence", "insufficient", None),
    ]
    with pytest.raises((TypeError, ValueError, AttributeError)):
        limitations[0].lens_id = "changed"
    empty = ObservationReasoningInput.model_construct(
        context=ObservationSemanticContext(
            identity=identity,
            name="Observation",
            lenses=(ReasoningLens(lens_id="usable", lens_type="metric"),),
        ),
        usable_results=(),
        unavailable_lenses=(),
        relationships=(),
    )
    assert derive_limitations(empty) == ()
