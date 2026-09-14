"""Pure projections for Observation-level Relationship and reasoning stages."""

from __future__ import annotations

import json
from collections.abc import Sequence
from uuid import UUID

from pydantic import TypeAdapter

from app.execution.contracts import (
    AlertLensSnapshot,
    CollectedLensOutcome,
    LensOutcomePartition,
    MetricLensSnapshot,
    ObservationExecutionSnapshot,
)
from app.execution.ordering import canonical_lens_order
from app.infrastructure.persistence.runtime_contracts import LensAnalysisResultInput
from app.observations.contracts import (
    RelationshipCreate,
    SemanticDescriptor,
    TrendDescriptor,
    VariabilityDescriptor,
)
from app.reasoning.contracts import (
    ObservationAnalysisResult,
    ObservationIdentity,
    ObservationReasoningInput,
    ObservationSemanticContext,
    ReasoningLens,
    UnavailableLens,
)
from app.reasoning.input import insufficient_metric_as_unavailable, validate_input
from app.relationships.contracts import RelationshipEvaluation
from app.reporting.contracts import (
    ReportAnalysisWindow,
    ReportGenerationRequest,
    ReportSemanticContext,
)


def relationship_definitions(
    snapshot: ObservationExecutionSnapshot,
) -> tuple[RelationshipCreate, ...]:
    """Project frozen Relationship definitions while preserving configured order."""
    return tuple(
        RelationshipCreate(
            id=item.relationship_id,
            name=item.name,
            description=item.description,
            participants=list(item.participants),
            conditions={key: _semantic_descriptor(value) for key, value in item.conditions},
            expected={key: _semantic_descriptor(value) for key, value in item.expected},
        )
        for item in snapshot.relationships
    )


def admissible_artifacts(
    outcomes: Sequence[CollectedLensOutcome],
    snapshot: ObservationExecutionSnapshot | None = None,
) -> tuple[LensAnalysisResultInput, ...]:
    """Return every admissible current-run artifact, omitting failed Alerts only."""
    artifacts: list[LensAnalysisResultInput] = []
    if snapshot is None:
        ordered = tuple(outcomes)
    else:
        order = {
            (lens.lens_type, lens.lens_id): index
            for index, lens in enumerate(canonical_lens_order(snapshot))
        }
        ordered = sorted(
            outcomes,
            key=lambda item: order[(item.assignment.lens.lens_type, item.assignment.lens.lens_id)],
        )
    for outcome in ordered:
        if outcome.artifact is None:
            continue
        artifacts.append(outcome.artifact.to_persistence_envelope())
    return tuple(artifacts)


def validate_relationship_batch(
    snapshot: ObservationExecutionSnapshot,
    evaluations: Sequence[object],
    *,
    observation_id: UUID,
    observation_run_id: UUID,
) -> tuple[object, ...]:
    """Validate exact ordered Relationship identity and current-run correlation."""
    expected = tuple(item.relationship_id for item in snapshot.relationships)
    if len(evaluations) != len(expected):
        raise ValueError("Relationship evaluation batch cardinality differs from definitions")
    adapter = TypeAdapter(RelationshipEvaluation)
    try:
        validated = tuple(adapter.validate_python(item) for item in evaluations)
    except Exception as exc:
        raise ValueError("Relationship evaluation batch identity or order is invalid") from exc
    ids = tuple(item.relationship_id for item in validated)
    if ids != expected or len(set(ids)) != len(ids):
        raise ValueError("Relationship evaluation batch identity or order is invalid")
    # Relationship evaluations intentionally have no run identity.  The correlation
    # boundary is established by the stage's current ObservationRun validation.
    if not isinstance(observation_id, UUID) or not isinstance(observation_run_id, UUID):
        raise ValueError("Relationship evaluation requires current-run identity")
    return validated


def build_observation_reasoning_input(
    snapshot: ObservationExecutionSnapshot,
    partition: LensOutcomePartition,
    evaluations: Sequence[object],
    *,
    observation_run_id: UUID,
) -> ObservationReasoningInput:
    """Build the exact canonical-order reasoning partition from a completed JOIN."""
    context = ObservationSemanticContext(
        identity=ObservationIdentity(
            observation_id=snapshot.observation_id,
            observation_run_id=observation_run_id,
        ),
        name=snapshot.name,
        description=snapshot.description,
        analytical_objective=snapshot.objective,
        operational_context=snapshot.operational_context,
        lenses=tuple(_reasoning_lens(item) for item in _canonical_lenses(snapshot)),
    )
    order = {
        (lens.lens_type, lens.lens_id): index
        for index, lens in enumerate(canonical_lens_order(snapshot))
    }
    ordered_usable = sorted(
        partition.usable,
        key=lambda item: order[(item.assignment.lens.lens_type, item.assignment.lens.lens_id)],
    )
    ordered_unavailable = sorted(
        partition.unavailable,
        key=lambda item: order[(item.assignment.lens.lens_type, item.assignment.lens.lens_id)],
    )
    usable = tuple(_usable_result(outcome) for outcome in ordered_usable)
    unavailable = tuple(_unavailable_result(outcome) for outcome in ordered_unavailable)
    return validate_input(
        ObservationReasoningInput(
            context=context,
            usable_results=usable,
            unavailable_lenses=unavailable,
            relationships=tuple(evaluations),
        )
    )


def validate_reasoning_success(
    result: ObservationAnalysisResult,
    *,
    observation_id: UUID,
    observation_run_id: UUID,
) -> ObservationAnalysisResult:
    """Require a successful reasoning result to correlate exactly to the current run."""
    if (
        result.identity.observation_id != observation_id
        or result.identity.observation_run_id != observation_run_id
    ):
        raise ValueError("Observation reasoning result identity does not match current run")
    return result


def report_generation_request(
    snapshot: ObservationExecutionSnapshot,
    result: ObservationAnalysisResult,
) -> ReportGenerationRequest:
    """Project the frozen semantic context and exact observed window for reporting."""
    if snapshot.observation_id != result.identity.observation_id:
        raise ValueError("Report analysis result observation identity does not match snapshot")
    return ReportGenerationRequest(
        context=ReportSemanticContext(
            identity=result.identity,
            name=snapshot.name,
            description=snapshot.description,
            analytical_objective=snapshot.objective,
            operational_context=snapshot.operational_context,
        ),
        analysis_result=result,
        analysis_window=ReportAnalysisWindow(
            **{"from": snapshot.analysis_window.from_, "to": snapshot.analysis_window.to}
        ),
    )


def _semantic_descriptor(value) -> SemanticDescriptor:
    return SemanticDescriptor(
        trend=None
        if value.trend_direction is None and value.trend_rate is None
        else TrendDescriptor(direction=value.trend_direction, rate=value.trend_rate),
        variability=None
        if value.variability_state is None
        else VariabilityDescriptor(state=value.variability_state),
    )


def _canonical_lenses(snapshot: ObservationExecutionSnapshot):
    return canonical_lens_order(snapshot)


def _reasoning_lens(lens: MetricLensSnapshot | AlertLensSnapshot) -> ReasoningLens:
    return ReasoningLens(
        lens_id=lens.lens_id,
        lens_type=lens.lens_type,
        name=lens.name,
        description=lens.description,
        analysis_objectives=lens.analysis_objectives,
    )


def _usable_result(outcome: CollectedLensOutcome):
    if outcome.artifact is None:
        raise ValueError("usable outcome lacks artifact")
    envelope = outcome.artifact.to_persistence_envelope()
    adapter: TypeAdapter = TypeAdapter(
        __import__("app.reasoning.contracts", fromlist=["UsableLensResult"]).UsableLensResult
    )
    return _validate_json_roundtrip(envelope.payload, adapter)


def _unavailable_result(outcome: CollectedLensOutcome) -> UnavailableLens:
    if isinstance(outcome.assignment.lens, MetricLensSnapshot):
        if outcome.status == "completed":
            if (
                outcome.artifact is None
                or outcome.artifact.to_persistence_envelope().payload.get("data_quality")
                != "insufficient"
            ):
                raise ValueError("completed Metric unavailable outcome is not insufficient")
            from app.metrics.contracts import CompletedInsufficientMetricResult

            adapter = TypeAdapter(CompletedInsufficientMetricResult)
            return insufficient_metric_as_unavailable(
                _validate_json_roundtrip(
                    outcome.artifact.to_persistence_envelope().payload,
                    adapter,
                )
            )
    if outcome.reason is None:
        raise ValueError("unavailable outcome requires a reason")
    return UnavailableLens(
        lens_id=outcome.assignment.lens.lens_id,
        lens_type=outcome.assignment.lens.lens_type,
        origin="caller_unavailable",
        reason={"code": outcome.reason.code, "component": outcome.reason.component},
    )


def _validate_json_roundtrip(payload: dict, adapter: TypeAdapter):
    """Validate a persisted payload strictly, then retry through its JSON representation."""
    try:
        return adapter.validate_python(payload)
    except (TypeError, ValueError):
        try:
            return adapter.validate_json(json.dumps(payload))
        except (TypeError, ValueError) as json_error:
            raise ValueError("persisted Lens result payload is invalid") from json_error
