"""Immutable application contracts for one Observation execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Literal, Protocol
from uuid import UUID

from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensResultIdentity,
    LensRunStatus,
    LensType,
)

type PreparationRejectionCode = Literal[
    "invalid_execution_request",
    "observation_not_found",
    "invalid_observation_definition",
    "empty_lens_topology",
    "unsupported_lens_type",
]
type LensTerminalStatus = Literal["completed", "partial", "failed"]


@dataclass(frozen=True, slots=True)
class ExecutionReason:
    """Compact framework-neutral reason compatible with runtime lifecycle metadata."""

    code: str
    component: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("execution reason code must be non-empty")
        if self.component is not None and (
            not isinstance(self.component, str) or not self.component.strip()
        ):
            raise ValueError("execution reason component must be non-empty when present")


@dataclass(frozen=True, slots=True)
class AnalysisWindow:
    """Exact UTC interval used as the analysis scope for one execution."""

    from_: datetime
    to: datetime


@dataclass(frozen=True, slots=True)
class ObservationExecutionRequest:
    """Minimal internal request to execute one predefined Observation."""

    observation_id: UUID
    analysis_window: AnalysisWindow


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """Caller-supplied bounds for one Observation execution."""

    max_parallel_lens_runs: int
    lens_deadline_seconds: float


@dataclass(frozen=True, slots=True)
class MetricLensSnapshot:
    """Detached Metric definition fields required by its execution pipeline."""

    lens_id: str
    name: str
    description: str | None
    metric_id: str
    adapter_type: Literal["prometheus"]
    source_id: str
    query: str
    unit: str
    analysis_objectives: tuple[str, ...]
    reference_periods: tuple[str, ...]
    lens_type: Literal["metric"] = "metric"


@dataclass(frozen=True, slots=True)
class AlertLensSnapshot:
    """Detached Alert definition fields required by its execution pipeline."""

    lens_id: str
    name: str
    description: str | None
    source: Literal["jira_track_and_release"]
    selector_query: str
    analysis_objectives: tuple[str, ...]
    reference_periods: tuple[str, ...]
    lens_type: Literal["alert"] = "alert"


@dataclass(frozen=True, slots=True)
class SemanticDescriptorSnapshot:
    """Detached semantic relationship descriptor for one Metric participant."""

    trend_direction: str | None
    trend_rate: str | None
    variability_state: str | None


@dataclass(frozen=True, slots=True)
class RelationshipSnapshot:
    """Detached ordered Relationship definition for post-Lens evaluation."""

    relationship_id: str
    name: str
    description: str | None
    participants: tuple[str, ...]
    conditions: tuple[tuple[str, SemanticDescriptorSnapshot], ...]
    expected: tuple[tuple[str, SemanticDescriptorSnapshot], ...]


@dataclass(frozen=True, slots=True)
class ObservationExecutionSnapshot:
    """Complete detached definition scope frozen for one future execution."""

    observation_id: UUID
    schema_version: int
    analysis_window: AnalysisWindow
    name: str
    description: str | None
    objective: str
    metric_lenses: tuple[MetricLensSnapshot, ...]
    alert_lenses: tuple[AlertLensSnapshot, ...]
    relationships: tuple[RelationshipSnapshot, ...]


@dataclass(frozen=True, slots=True)
class LensExecutionAssignment:
    """One initialized type-aware Lens runtime identity and its frozen definition."""

    observation_id: UUID
    observation_run_id: UUID
    lens_run_id: UUID
    analysis_window: AnalysisWindow
    lens: MetricLensSnapshot | AlertLensSnapshot


@dataclass(frozen=True, slots=True)
class CollectedLensResultIdentity:
    """Detached identity retained with one collected durable Lens artifact."""

    observation_id: UUID
    observation_run_id: UUID
    lens_id: str
    lens_run_id: UUID
    metric_ref: str | None
    unit: str | None


@dataclass(frozen=True, slots=True)
class CollectedLensArtifact:
    """Immutable, detached projection of the exact terminal artifact persistence returned."""

    result_type: LensType
    status: LensRunStatus
    schema_version: str
    identity: CollectedLensResultIdentity
    provenance: Mapping[str, object]
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        """Detach mappings supplied by either persistence or a later projection caller."""

        if not isinstance(self.identity, CollectedLensResultIdentity):
            raise ValueError("collected Lens artifact requires a detached identity")
        if not isinstance(self.provenance, Mapping) or not isinstance(self.payload, Mapping):
            raise ValueError("collected Lens artifact requires mapping provenance and payload")
        object.__setattr__(self, "provenance", _freeze_mapping(self.provenance))
        object.__setattr__(self, "payload", _freeze_mapping(self.payload))
        self.to_persistence_envelope()

    @classmethod
    def from_persistence_envelope(cls, envelope: LensAnalysisResultInput) -> CollectedLensArtifact:
        """Detach and recursively freeze a validated persistence envelope."""

        validated = LensAnalysisResultInput.model_validate(envelope.model_dump(mode="json"))
        identity = validated.identity
        return cls(
            result_type=validated.result_type,
            status=validated.status,
            schema_version=validated.schema_version,
            identity=CollectedLensResultIdentity(
                observation_id=identity.observation_id,
                observation_run_id=identity.observation_run_id,
                lens_id=identity.lens_id,
                lens_run_id=identity.lens_run_id,
                metric_ref=identity.metric_ref,
                unit=identity.unit,
            ),
            provenance=validated.provenance,
            payload=validated.payload,
        )

    def to_persistence_envelope(self) -> LensAnalysisResultInput:
        """Return an independent mutable envelope for a later in-memory projection."""

        return LensAnalysisResultInput(
            result_type=self.result_type,
            status=self.status,
            schema_version=self.schema_version,
            identity=LensResultIdentity(
                observation_id=self.identity.observation_id,
                observation_run_id=self.identity.observation_run_id,
                lens_id=self.identity.lens_id,
                lens_run_id=self.identity.lens_run_id,
                metric_ref=self.identity.metric_ref,
                unit=self.identity.unit,
            ),
            provenance=_thaw_mapping(self.provenance),
            payload=_thaw_mapping(self.payload),
        )


@dataclass(frozen=True, slots=True)
class CollectedLensOutcome:
    """Compact terminal Lens result collected after its durable terminal write."""

    assignment: LensExecutionAssignment
    status: LensTerminalStatus
    artifact: CollectedLensArtifact | LensAnalysisResultInput | None = None
    reason: ExecutionReason | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.assignment, LensExecutionAssignment):
            raise ValueError("collected Lens outcome requires a Lens execution assignment")
        if self.status not in {"completed", "partial", "failed"}:
            raise ValueError("collected Lens outcome must be terminal")
        if self.status == "completed" and self.reason is not None:
            raise ValueError("completed Lens outcome cannot carry a reason")
        if self.status in {"partial", "failed"} and type(self.reason) is not ExecutionReason:
            raise ValueError("partial and failed Lens outcomes require an execution reason")
        artifact = _validate_collected_artifact(self.assignment, self.status, self.artifact)
        object.__setattr__(self, "artifact", artifact)


def _validate_collected_artifact(
    assignment: LensExecutionAssignment,
    status: LensTerminalStatus,
    artifact: CollectedLensArtifact | LensAnalysisResultInput | None,
) -> CollectedLensArtifact | None:
    """Require the exact durable artifact shape for one terminal Lens variant."""

    is_metric = isinstance(assignment.lens, MetricLensSnapshot)
    if artifact is None:
        if not is_metric and status == "failed":
            return None
        raise ValueError("collected Lens outcome requires its terminal artifact")
    if isinstance(artifact, LensAnalysisResultInput):
        artifact = CollectedLensArtifact.from_persistence_envelope(artifact)
    if not isinstance(artifact, CollectedLensArtifact):
        raise ValueError("collected Lens outcome artifact must be a validated persistence envelope")
    expected_type = LensType.METRIC if is_metric else LensType.ALERT
    expected_status = LensRunStatus(status)
    identity = artifact.identity
    if (
        artifact.result_type is not expected_type
        or artifact.status is not expected_status
        or identity.observation_id != assignment.observation_id
        or identity.observation_run_id != assignment.observation_run_id
        or identity.lens_id != assignment.lens.lens_id
        or identity.lens_run_id != assignment.lens_run_id
    ):
        raise ValueError("collected Lens outcome artifact contradicts its assignment or status")
    if is_metric:
        assert isinstance(assignment.lens, MetricLensSnapshot)
        if (
            identity.metric_ref != assignment.lens.metric_id
            or identity.unit != assignment.lens.unit
        ):
            raise ValueError("collected Metric artifact identity contradicts its assignment")
    elif status == "failed":
        raise ValueError("failed Alert outcome cannot carry an artifact")
    return artifact


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Recursively detach JSON-compatible mapping content into immutable values."""

    return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})


def _freeze_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise ValueError("collected Lens artifact contains a non-JSON value")


def _thaw_mapping(value: Mapping[str, object]) -> dict[str, object]:
    """Recreate a mutable JSON-compatible mapping without exposing collected state."""

    return {key: _thaw_value(item) for key, item in value.items()}


def _thaw_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _thaw_mapping(value)
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class CompletedObservationExecutionOutcome:
    """Successful terminal outcome for an initialized ObservationRun."""

    observation_run_id: UUID
    kind: Literal["completed"] = "completed"
    status: Literal["completed"] = "completed"

    def __post_init__(self) -> None:
        if not isinstance(self.observation_run_id, UUID):
            raise ValueError("completed outcome requires a UUID observation run ID")
        if self.kind != "completed" or self.status != "completed":
            raise ValueError("completed outcome has a fixed kind and status")


@dataclass(frozen=True, slots=True)
class FailedObservationExecutionOutcome:
    """Failed terminal outcome for an initialized ObservationRun."""

    observation_run_id: UUID
    reason: ExecutionReason
    kind: Literal["failed"] = "failed"
    status: Literal["failed"] = "failed"

    def __post_init__(self) -> None:
        if not isinstance(self.observation_run_id, UUID):
            raise ValueError("failed outcome requires a UUID observation run ID")
        if not isinstance(self.reason, ExecutionReason):
            raise ValueError("failed outcome requires an execution reason")
        if self.kind != "failed" or self.status != "failed":
            raise ValueError("failed outcome has a fixed kind and status")


@dataclass(frozen=True, slots=True)
class RejectedObservationExecutionOutcome:
    """Controlled rejection produced before any ObservationRun is initialized."""

    reason: ExecutionReason
    kind: Literal["rejected"] = "rejected"

    def __post_init__(self) -> None:
        if self.kind != "rejected":
            raise ValueError("rejected outcome has a fixed kind")
        if type(self.reason) is not ExecutionReason:
            raise ValueError("rejected outcome requires an execution reason")
        if self.reason.component != "execution_preparation" or self.reason.code not in {
            "invalid_execution_request",
            "observation_not_found",
            "invalid_observation_definition",
            "empty_lens_topology",
            "unsupported_lens_type",
        }:
            raise ValueError("rejected outcome requires a controlled preparation reason")


type ObservationExecutionOutcome = (
    CompletedObservationExecutionOutcome
    | FailedObservationExecutionOutcome
    | RejectedObservationExecutionOutcome
)
type PreparationResult = ObservationExecutionSnapshot | RejectedObservationExecutionOutcome


class ObservationDefinitionLoader(Protocol):
    """Load one complete Observation definition aggregate exactly once."""

    async def get(self, session: object, observation_id: UUID) -> object | None:
        """Return the complete aggregate, or ``None`` when it is absent."""


class LensExecutionAdapter(Protocol):
    """Execute one admitted Lens assignment behind its type-specific boundary."""

    async def execute(
        self, assignment: LensExecutionAssignment, policy: ExecutionPolicy
    ) -> CollectedLensOutcome:
        """Return the durable terminal outcome for the supplied assignment."""


def project_observation_execution(
    request: object,
    policy: object,
    definition: object | None,
) -> PreparationResult:
    """Validate inputs and freeze one loaded aggregate into immutable execution values."""

    if not _is_valid_request(request) or not _is_valid_policy(policy):
        return _rejected("invalid_execution_request")
    assert isinstance(request, ObservationExecutionRequest)
    if definition is None:
        return _rejected("observation_not_found")
    try:
        return _project_definition(request, definition)
    except _EmptyTopology:
        return _rejected("empty_lens_topology")
    except _UnsupportedLens:
        return _rejected("unsupported_lens_type")
    except (AttributeError, TypeError, ValueError):
        return _rejected("invalid_observation_definition")


def _is_valid_request(request: object) -> bool:
    if not isinstance(request, ObservationExecutionRequest):
        return False
    if not isinstance(request.observation_id, UUID) or not isinstance(
        request.analysis_window, AnalysisWindow
    ):
        return False
    return (
        _is_utc(request.analysis_window.from_)
        and _is_utc(request.analysis_window.to)
        and (request.analysis_window.from_ < request.analysis_window.to)
    )


def _is_valid_policy(policy: object) -> bool:
    if not isinstance(policy, ExecutionPolicy):
        return False
    if (
        isinstance(policy.max_parallel_lens_runs, bool)
        or not isinstance(policy.max_parallel_lens_runs, int)
        or policy.max_parallel_lens_runs <= 0
    ):
        return False
    if isinstance(policy.lens_deadline_seconds, bool) or not isinstance(
        policy.lens_deadline_seconds, (int, float)
    ):
        return False
    return policy.lens_deadline_seconds > 0 and policy.lens_deadline_seconds != float("inf")


def _is_utc(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is UTC


def _project_definition(
    request: ObservationExecutionRequest, definition: object
) -> ObservationExecutionSnapshot:
    observation_id = _required_uuid(definition, "id")
    if observation_id != request.observation_id:
        raise ValueError("loaded definition identity differs from request")
    metric_models = _tuple_attribute(definition, "lenses")
    alert_models = _tuple_attribute(definition, "alert_lenses")
    relationship_models = _tuple_attribute(definition, "relationships")
    _reject_unsupported_collections(definition)
    if not metric_models and not alert_models:
        raise _EmptyTopology()
    metrics = tuple(_metric_snapshot(model) for model in metric_models)
    alerts = tuple(_alert_snapshot(model) for model in alert_models)
    _validate_lens_ids(metrics, alerts)
    relationships = tuple(_relationship_snapshot(model) for model in relationship_models)
    _validate_relationships(relationships, metrics)
    return ObservationExecutionSnapshot(
        observation_id=observation_id,
        schema_version=_positive_int(definition, "schema_version"),
        analysis_window=request.analysis_window,
        name=_non_empty(definition, "name"),
        description=_optional_text(definition, "description"),
        objective=_non_empty(definition, "objective"),
        metric_lenses=metrics,
        alert_lenses=alerts,
        relationships=relationships,
    )


def _reject_unsupported_collections(definition: object) -> None:
    for name in ("log_lenses", "unsupported_lenses"):
        lenses = getattr(definition, name, ())
        if lenses:
            raise _UnsupportedLens()


def _metric_snapshot(model: object) -> MetricLensSnapshot:
    lens_type = getattr(model, "lens_type", getattr(model, "type", "metric"))
    if lens_type != "metric":
        raise _UnsupportedLens()
    adapter_type = _non_empty(model, "adapter_type")
    if adapter_type != "prometheus":
        raise ValueError("unsupported Metric adapter")
    return MetricLensSnapshot(
        lens_id=_non_empty(model, "lens_id"),
        name=_non_empty(model, "name"),
        description=_optional_text(model, "description"),
        metric_id=_non_empty(model, "metric_id"),
        adapter_type="prometheus",
        source_id=_non_empty(model, "source_id"),
        query=_non_empty(model, "query"),
        unit=_non_empty(model, "unit"),
        analysis_objectives=_string_tuple(model, "analysis_objectives"),
        reference_periods=_string_tuple(model, "reference_periods"),
    )


def _alert_snapshot(model: object) -> AlertLensSnapshot:
    lens_type = getattr(model, "lens_type", getattr(model, "type", "alert"))
    if lens_type != "alert":
        raise _UnsupportedLens()
    source = _non_empty(model, "source")
    if source != "jira_track_and_release":
        raise ValueError("unsupported Alert source")
    return AlertLensSnapshot(
        lens_id=_non_empty(model, "lens_id"),
        name=_non_empty(model, "name"),
        description=_optional_text(model, "description"),
        source="jira_track_and_release",
        selector_query=_non_empty(model, "selector_query"),
        analysis_objectives=_string_tuple(model, "analysis_objectives"),
        reference_periods=_string_tuple(model, "reference_periods"),
    )


def _relationship_snapshot(model: object) -> RelationshipSnapshot:
    participants = _string_tuple(model, "participants")
    if len(participants) < 2 or len(set(participants)) != len(participants):
        raise ValueError("invalid relationship participants")
    conditions = _descriptor_items(model.conditions)
    expected = _descriptor_items(model.expected)
    if not expected:
        raise ValueError("relationship needs expected semantics")
    return RelationshipSnapshot(
        relationship_id=_non_empty(model, "relationship_id"),
        name=_non_empty(model, "name"),
        description=_optional_text(model, "description"),
        participants=participants,
        conditions=conditions,
        expected=expected,
    )


def _descriptor_items(value: object) -> tuple[tuple[str, SemanticDescriptorSnapshot], ...]:
    if not isinstance(value, Mapping):
        raise ValueError("relationship descriptors must be mappings")
    return tuple((_non_empty_value(key), _descriptor_snapshot(item)) for key, item in value.items())


def _descriptor_snapshot(value: object) -> SemanticDescriptorSnapshot:
    if not isinstance(value, Mapping):
        raise ValueError("relationship descriptor must be a mapping")
    trend = value.get("trend")
    variability = value.get("variability")
    if trend is not None and not isinstance(trend, Mapping):
        raise ValueError("relationship trend must be a mapping")
    if variability is not None and not isinstance(variability, Mapping):
        raise ValueError("relationship variability must be a mapping")
    direction = _optional_mapping_text(trend, "direction")
    rate = _optional_mapping_text(trend, "rate")
    state = _optional_mapping_text(variability, "state")
    if direction is None and rate is None and state is None:
        raise ValueError("relationship descriptor must contain semantics")
    return SemanticDescriptorSnapshot(direction, rate, state)


def _validate_lens_ids(
    metrics: tuple[MetricLensSnapshot, ...], alerts: tuple[AlertLensSnapshot, ...]
) -> None:
    if len({lens.lens_id for lens in metrics}) != len(metrics):
        raise ValueError("duplicate Metric Lens identity")
    if len({lens.lens_id for lens in alerts}) != len(alerts):
        raise ValueError("duplicate Alert Lens identity")


def _validate_relationships(
    relationships: tuple[RelationshipSnapshot, ...], metrics: tuple[MetricLensSnapshot, ...]
) -> None:
    if len({relationship.relationship_id for relationship in relationships}) != len(relationships):
        raise ValueError("duplicate Relationship identity")
    metric_ids = {lens.lens_id for lens in metrics}
    for relationship in relationships:
        referenced = {key for key, _ in relationship.conditions} | {
            key for key, _ in relationship.expected
        }
        participants = set(relationship.participants)
        if not participants <= metric_ids or referenced != participants:
            raise ValueError("invalid Relationship participant topology")


def _tuple_attribute(value: object, name: str) -> tuple[object, ...]:
    candidate = getattr(value, name)
    if isinstance(candidate, (str, bytes)):
        raise ValueError(f"{name} must be a collection")
    return tuple(candidate)


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    items = _tuple_attribute(value, name)
    normalized = tuple(_non_empty_value(item) for item in items)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} contains duplicates")
    return normalized


def _required_uuid(value: object, name: str) -> UUID:
    candidate = getattr(value, name)
    if not isinstance(candidate, UUID):
        raise ValueError(f"{name} must be a UUID")
    return candidate


def _positive_int(value: object, name: str) -> int:
    candidate = getattr(value, name)
    if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate <= 0:
        raise ValueError(f"{name} must be positive")
    return candidate


def _non_empty(value: object, name: str) -> str:
    return _non_empty_value(getattr(value, name))


def _non_empty_value(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("text must be non-empty")
    return value


def _optional_text(value: object, name: str) -> str | None:
    candidate = getattr(value, name)
    if candidate is None:
        return None
    return _non_empty_value(candidate)


def _optional_mapping_text(value: Mapping[object, object] | None, key: str) -> str | None:
    if value is None or key not in value:
        return None
    return _non_empty_value(value[key])


def _rejected(code: PreparationRejectionCode) -> RejectedObservationExecutionOutcome:
    return RejectedObservationExecutionOutcome(
        reason=ExecutionReason(code=code, component="execution_preparation")
    )


class _EmptyTopology(ValueError):
    pass


class _UnsupportedLens(ValueError):
    pass
