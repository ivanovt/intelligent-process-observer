"""Correlate and validate native evidence before any reasoning invocation."""
# ruff: noqa: E501

from __future__ import annotations

from app.alerts.contracts import PartialAlertAnalysisResult
from app.metrics.contracts import CompletedInsufficientMetricResult, PartialMetricResult
from app.reasoning.contracts import (
    ObservationReasoningInput,
    UnavailableLens,
)


def validate_input(value: ObservationReasoningInput) -> ObservationReasoningInput:
    """Enforce exact supported-Lens correlation and availability partitioning."""
    context = value.context
    if any(lens.lens_type == "log" for lens in context.lenses):
        raise ValueError("Log Lens contexts are not supported by Observation reasoning")
    expected = {(lens.lens_type, lens.lens_id) for lens in context.lenses}
    usable: set[tuple[str, str]] = set()
    for result in value.usable_results:
        identity = result.identity
        lens_type = result.lens_type
        if (
            identity.observation_id != context.identity.observation_id
            or identity.observation_run_id != context.identity.observation_run_id
        ):
            raise ValueError("usable result identity must match reasoning context")
        key = (lens_type, identity.lens_id)
        if key in usable:
            raise ValueError("usable results must not contain duplicate Lens identities")
        usable.add(key)
    unavailable: set[tuple[str, str]] = set()
    for item in value.unavailable_lenses:
        key = (item.lens_type, item.lens_id)
        if key in unavailable:
            raise ValueError("unavailable lenses must not contain duplicate Lens identities")
        unavailable.add(key)
    if usable & unavailable:
        raise ValueError("usable and unavailable Lens collections must not overlap")
    if usable | unavailable != expected:
        raise ValueError("usable and unavailable collections must exactly partition context Lenses")
    if not usable:
        raise ValueError("Observation reasoning requires at least one usable result")
    if len({relationship.relationship_id for relationship in value.relationships}) != len(
        value.relationships
    ):
        raise ValueError("relationship ids must be unique")
    return value


def insufficient_metric_as_unavailable(
    result: CompletedInsufficientMetricResult,
) -> UnavailableLens:
    """Project a completed insufficient Metric into deterministic unavailable metadata."""
    return UnavailableLens(
        lens_id=result.identity.lens_id,
        lens_type="metric",
        origin="completed_insufficient_metric",
        reason={"code": "insufficient_data"},
    )


def derive_limitations(value: ObservationReasoningInput):
    """Return deterministic availability limitations in semantic Lens order."""
    partials = {
        (item.lens_type, item.identity.lens_id): item
        for item in value.usable_results
        if isinstance(item, (PartialMetricResult, PartialAlertAnalysisResult))
    }
    unavailable = {(item.lens_type, item.lens_id): item for item in value.unavailable_lenses}
    limitations = []
    for lens in value.context.lenses:
        identity = (lens.lens_type, lens.lens_id)
        if identity in unavailable:
            code = (
                "insufficient_lens_evidence"
                if unavailable[identity].origin == "completed_insufficient_metric"
                else "missing_lens_evidence"
            )
            limitations.append(
                {
                    "code": code,
                    "lens_id": lens.lens_id,
                    "lens_type": lens.lens_type,
                }
            )
        elif identity in partials:
            reason = partials[identity].reason
            limitations.append(
                {
                    "code": "partial_lens_analysis",
                    "lens_id": lens.lens_id,
                    "lens_type": lens.lens_type,
                    "component": reason.component,
                }
            )
    from pydantic import TypeAdapter

    from app.reasoning.contracts import Limitation

    return tuple(TypeAdapter(Limitation).validate_python(item) for item in limitations)
