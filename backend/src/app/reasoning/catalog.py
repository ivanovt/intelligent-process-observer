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


def _allowed_alert_locator(locator: tuple[str | int, ...]) -> bool:
    """Keep provider/source metadata out of citeable Alert evidence."""
    return "source_ref" not in locator and locator[-1] != "source"


def build_catalog(value: ObservationReasoningInput) -> tuple[EvidenceCatalogEntry, ...]:
    """Project evidence-only leaves in stable supplied-source order."""
    entries: list[EvidenceCatalogEntry] = []

    def add(
        source_type: str, source_id: object, artifact: dict[str, Any], roots: tuple[str, ...]
    ) -> None:
        for root in roots:
            if root not in artifact or artifact[root] is None:
                continue
            for locator in _walk(artifact[root], (root,)):
                if source_type == "alert_result" and not _allowed_alert_locator(locator):
                    continue
                entries.append(
                    EvidenceCatalogEntry(
                        id=f"evidence_{len(entries) + 1:04d}",
                        reference=EvidenceReference(
                            source_type=source_type, source_id=source_id, locator=locator
                        ),
                    )
                )

    for result in value.usable_results:
        raw = result.model_dump(mode="json")
        if result.lens_type == "metric":
            add(
                "metric_result",
                result.identity.lens_run_id,
                raw,
                ("current_state", "reference_periods", "history", "evidence"),
            )
        else:
            add(
                "alert_result",
                result.identity.lens_run_id,
                raw,
                (
                    "alerts",
                    "alert_activity",
                    "status_distribution",
                    "duration_statistics",
                    "provider_importance_distribution",
                    "comparisons",
                    "findings",
                    "overall_importance",
                ),
            )
    for relationship in value.relationships:
        add(
            "relationship_evaluation",
            relationship.relationship_id,
            relationship.model_dump(mode="json"),
            ("applicability", "state", "conditions", "expectations"),
        )
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
