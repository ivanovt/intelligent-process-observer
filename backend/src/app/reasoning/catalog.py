"""Deterministic evidence-catalog projection and reference resolution."""

# ruff: noqa: E501
from __future__ import annotations

from typing import Any

from app.reasoning.contracts import (
    EvidenceCatalogEntry,
    EvidenceReference,
    ObservationReasoningInput,
)


def _walk(value: Any, prefix: tuple[str | int, ...] = ()) -> tuple[tuple[str | int, ...], ...]:
    if value is None:
        return ()
    if isinstance(value, dict):
        return tuple(item for key, child in value.items() for item in _walk(child, prefix + (key,)))
    if isinstance(value, list):
        return tuple(
            item for index, child in enumerate(value) for item in _walk(child, prefix + (index,))
        )
    return (prefix,)


def build_catalog(value: ObservationReasoningInput) -> tuple[EvidenceCatalogEntry, ...]:
    """Project source-specific evidence in stable supplied-source order."""
    entries: list[EvidenceCatalogEntry] = []

    def add_locator(source_type: str, source_id: object, locator: tuple[str | int, ...]) -> None:
        entries.append(
            EvidenceCatalogEntry(
                id=f"evidence_{len(entries) + 1:04d}",
                reference=EvidenceReference(
                    source_type=source_type, source_id=source_id, locator=locator
                ),
            )
        )

    def add_leaves(
        source_type: str, source_id: object, artifact: dict[str, Any], roots: tuple[str, ...]
    ) -> None:
        for root in roots:
            if root not in artifact or artifact[root] is None:
                continue
            for locator in _walk(artifact[root], (root,)):
                add_locator(source_type, source_id, locator)

    def add_elements(
        source_type: str,
        source_id: object,
        artifact: dict[str, Any],
        root: str,
        prefix: tuple[str | int, ...] = (),
    ) -> None:
        items = artifact.get(root)
        if not isinstance(items, list):
            return
        for index in range(len(items)):
            add_locator(source_type, source_id, prefix + (root, index))

    for result in value.usable_results:
        raw = result.model_dump(mode="json")
        if result.lens_type == "metric":
            add_leaves(
                "metric_result",
                result.identity.lens_run_id,
                raw,
                ("current_state",),
            )
            add_elements("metric_result", result.identity.lens_run_id, raw, "reference_periods")
            evidence = raw.get("evidence")
            if isinstance(evidence, dict):
                if evidence.get("current") is not None:
                    for locator in _walk(evidence["current"], ("evidence", "current")):
                        add_locator("metric_result", result.identity.lens_run_id, locator)
                add_elements(
                    "metric_result",
                    result.identity.lens_run_id,
                    evidence,
                    "reference_periods",
                    ("evidence",),
                )
            add_leaves(
                "metric_result",
                result.identity.lens_run_id,
                raw,
                ("history",),
            )
            if isinstance(evidence, dict) and evidence.get("history") is not None:
                for locator in _walk(evidence["history"], ("evidence", "history")):
                    add_locator("metric_result", result.identity.lens_run_id, locator)
        else:
            source_type, source_id = "alert_result", result.identity.lens_run_id
            add_elements(source_type, source_id, raw, "alerts")
            add_leaves(
                source_type,
                source_id,
                raw,
                (
                    "alert_activity",
                    "status_distribution",
                    "duration_statistics",
                    "provider_importance_distribution",
                ),
            )
            add_elements(source_type, source_id, raw, "comparisons")
            add_elements(source_type, source_id, raw, "findings")
            if raw.get("overall_importance") is not None:
                add_locator(source_type, source_id, ("overall_importance",))
    for relationship in value.relationships:
        source_type, source_id = "relationship_evaluation", relationship.relationship_id
        raw = relationship.model_dump(mode="json")
        for root in ("applicability", "state"):
            if raw.get(root) is not None:
                add_locator(source_type, source_id, (root,))
        add_elements(source_type, source_id, raw, "conditions")
        add_elements(source_type, source_id, raw, "expectations")
    return tuple(entries)


def resolve_reference(reference: EvidenceReference, value: ObservationReasoningInput) -> object:
    """Resolve one catalog reference against exactly one admitted immutable artifact."""
    candidates: list[dict[str, Any]] = []
    if reference.source_type in {"metric_result", "alert_result"}:
        candidates = [
            r.model_dump(mode="json")
            for r in value.usable_results
            if str(r.identity.lens_run_id) == str(reference.source_id)
            and ("metric_result" if r.lens_type == "metric" else "alert_result")
            == reference.source_type
        ]
    else:
        candidates = [
            r.model_dump(mode="json")
            for r in value.relationships
            if r.relationship_id == reference.source_id
        ]
    if len(candidates) != 1:
        raise ValueError("evidence reference must resolve to exactly one source")
    current: object = candidates[0]
    for part in reference.locator:
        if isinstance(part, str) and isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(part, int) and isinstance(current, list) and part < len(current):
            current = current[part]
        else:
            raise ValueError("evidence reference locator is invalid")
    return current
