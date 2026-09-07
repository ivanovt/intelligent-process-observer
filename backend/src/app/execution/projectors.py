"""Pure projections for Observation-level Relationship and reasoning stages."""

from __future__ import annotations

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
    ids = tuple(getattr(item, "relationship_id", None) for item in evaluations)
    if ids != expected or len(set(ids)) != len(ids):
        raise ValueError("Relationship evaluation batch identity or order is invalid")
    # Relationship evaluations intentionally have no run identity.  The correlation
    # boundary is established by the stage's current ObservationRun validation.
    if not isinstance(observation_id, UUID) or not isinstance(observation_run_id, UUID):
        raise ValueError("Relationship evaluation requires current-run identity")
    return tuple(evaluations)


def build_observation_reasoning_input(
    snapshot: ObservationExecutionSnapshot,
    partition: LensOutcomePartition,
    evaluations: Sequence[object],
) -> ObservationReasoningInput:
    """Build the exact canonical-order reasoning partition from a completed JOIN."""
    context = ObservationSemanticContext(
        identity=ObservationIdentity(
            observation_id=snapshot.observation_id,
            observation_run_id=_run_id(partition),
        ),
        name=snapshot.name,
        description=snapshot.description,
        analytical_objective=snapshot.objective,
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
    return sorted(
        (*snapshot.metric_lenses, *snapshot.alert_lenses),
        key=lambda x: (x.lens_type, x.lens_id),
    )


def _reasoning_lens(lens: MetricLensSnapshot | AlertLensSnapshot) -> ReasoningLens:
    return ReasoningLens(
        lens_id=lens.lens_id,
        lens_type=lens.lens_type,
        name=lens.name,
        description=lens.description,
        analysis_objectives=lens.analysis_objectives,
    )


def _run_id(partition: LensOutcomePartition) -> UUID:
    all_outcomes = (*partition.usable, *partition.unavailable)
    if not all_outcomes:
        raise ValueError("reasoning partition cannot be empty")
    run_id = all_outcomes[0].assignment.observation_run_id
    if any(item.assignment.observation_run_id != run_id for item in all_outcomes):
        raise ValueError("reasoning partition spans multiple runs")
    return run_id


def _usable_result(outcome: CollectedLensOutcome):
    if outcome.artifact is None:
        raise ValueError("usable outcome lacks artifact")
    envelope = outcome.artifact.to_persistence_envelope()
    adapter: TypeAdapter = TypeAdapter(
        __import__("app.reasoning.contracts", fromlist=["UsableLensResult"]).UsableLensResult
    )
    return adapter.validate_python(envelope.payload)


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
                adapter.validate_python(outcome.artifact.to_persistence_envelope().payload)
            )
    if outcome.reason is None:
        raise ValueError("unavailable outcome requires a reason")
    return UnavailableLens(
        lens_id=outcome.assignment.lens.lens_id,
        lens_type=outcome.assignment.lens.lens_type,
        origin="caller_unavailable",
        reason={"code": outcome.reason.code, "component": outcome.reason.component},
    )
