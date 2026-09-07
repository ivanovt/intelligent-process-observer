"""Internal validation envelopes for durable runtime execution state and artifacts.

These models protect persistence-owned lifecycle and correlation invariants. They do
not replace the analytical artifact builders that own domain-specific payload semantics.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObservationRunStatus(StrEnum):
    """Lifecycle states supported by a durable Observation execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LensRunStatus(StrEnum):
    """Lifecycle states supported by one durable Lens execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LensType(StrEnum):
    METRIC = "metric"
    ALERT = "alert"
    LOG = "log"


class PersistenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StructuredReason(PersistenceModel):
    """Compact, machine-readable primary reason for partial, failed, or cancelled work."""

    code: str = Field(min_length=1)
    component: str | None = None


class ObservationRunInput(PersistenceModel):
    id: UUID = Field(default_factory=uuid4)
    observation_id: UUID
    status: Literal[ObservationRunStatus.PENDING] = ObservationRunStatus.PENDING
    reason: StructuredReason | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    execution_context: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class LensRunInput(PersistenceModel):
    id: UUID = Field(default_factory=uuid4)
    lens_id: str = Field(min_length=1)
    lens_type: LensType
    status: Literal[LensRunStatus.PENDING] = LensRunStatus.PENDING
    reason: StructuredReason | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    execution_context: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class LensResultIdentity(PersistenceModel):
    observation_id: UUID
    observation_run_id: UUID
    lens_id: str = Field(min_length=1)
    lens_run_id: UUID
    metric_ref: str | None = None
    unit: str | None = None


class LensAnalysisResultInput(PersistenceModel):
    """Envelope for one Lens artifact, validating only persistence-relevant consistency.

    Failed Metric results are durable traceability records, while failed Alert and Log
    runs deliberately have no result artifact. Completed and partial results remain the
    only downstream-usable artifacts.
    """

    result_type: LensType
    status: Literal[
        LensRunStatus.COMPLETED,
        LensRunStatus.PARTIAL,
        LensRunStatus.FAILED,
    ]
    schema_version: str = Field(min_length=1)
    identity: LensResultIdentity
    provenance: dict[str, Any]
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_type_status_combination(self) -> LensAnalysisResultInput:
        if (
            self.result_type in {LensType.ALERT, LensType.LOG}
            and self.status is LensRunStatus.FAILED
        ):
            raise ValueError("Alert and Log analysis results cannot have failed status")
        if self.payload.get("schema_version") != self.schema_version:
            raise ValueError("Lens analysis result payload schema_version does not match envelope")
        if self.payload.get("lens_type") != self.result_type.value:
            raise ValueError("Lens analysis result payload lens_type does not match envelope")
        payload_identity = self.payload.get("identity")
        if not isinstance(payload_identity, dict):
            raise ValueError("Lens analysis result payload must contain identity")
        expected_identity = {
            "observation_id": str(self.identity.observation_id),
            "observation_run_id": str(self.identity.observation_run_id),
            "lens_id": self.identity.lens_id,
            "lens_run_id": str(self.identity.lens_run_id),
        }
        if any(str(payload_identity.get(key)) != value for key, value in expected_identity.items()):
            raise ValueError("Lens analysis result payload identity does not match envelope")
        payload_provenance = self.payload.get("provenance")
        if not isinstance(payload_provenance, dict) or payload_provenance != self.provenance:
            raise ValueError("Lens analysis result payload provenance does not match envelope")

        if self.result_type is LensType.METRIC:
            self._validate_metric_contract(payload_identity)
        elif self.payload.get("status") != self.status.value:
            raise ValueError("Lens analysis result payload status does not match envelope")
        if self.status is LensRunStatus.PARTIAL:
            self._validate_partial_reason()
        return self

    def _validate_metric_contract(self, payload_identity: dict[str, Any]) -> None:
        """Check the minimum failed-Metric envelope without validating analytical evidence."""
        if not self.identity.metric_ref or not self.identity.unit:
            raise ValueError("MetricAnalysisResult requires metric_ref and unit")
        if (
            payload_identity.get("metric_ref") != self.identity.metric_ref
            or payload_identity.get("unit") != self.identity.unit
        ):
            raise ValueError("MetricAnalysisResult payload identity does not match envelope")

        payload_status = self.payload.get("status")
        if not isinstance(payload_status, dict) or payload_status.get("state") != self.status.value:
            raise ValueError("MetricAnalysisResult payload status does not match envelope")
        if self.status is not LensRunStatus.FAILED:
            return

        error = payload_status.get("error")
        if not isinstance(error, dict) or not error.get("code") or not error.get("message"):
            raise ValueError(
                "Failed MetricAnalysisResult requires status.error.code and status.error.message"
            )
        if not isinstance(self.payload.get("analysis_window"), dict):
            raise ValueError("Failed MetricAnalysisResult requires analysis_window")
        self._require_non_empty_fields(
            self.payload["analysis_window"],
            "Failed MetricAnalysisResult analysis_window",
            ("from", "to"),
        )
        self._require_non_empty_fields(
            self.provenance,
            "Failed MetricAnalysisResult provenance",
            ("source", "generated_at"),
        )

    def _validate_partial_reason(self) -> None:
        """Require the common short reason carried by every partial result contract."""
        try:
            StructuredReason.model_validate(self.payload.get("reason"))
        except ValueError as error:
            raise ValueError("Partial LensAnalysisResult requires a structured reason") from error

    @staticmethod
    def _require_non_empty_fields(
        payload: dict[str, Any], context: str, fields: tuple[str, ...]
    ) -> None:
        """Reject structurally empty required envelope fields without imposing domain rules."""
        if any(
            not isinstance(payload.get(field), str) or not payload[field].strip()
            for field in fields
        ):
            field_list = ", ".join(fields)
            raise ValueError(f"{context} requires non-empty {field_list}")


class RelationshipEvaluationInput(PersistenceModel):
    relationship_id: str = Field(min_length=1)
    payload: dict[str, Any]


class ObservationAnalysisIdentity(PersistenceModel):
    observation_id: UUID
    observation_run_id: UUID


class ObservationAnalysisResultInput(PersistenceModel):
    """Correlation envelope for an Observation analysis artifact, not its domain validator."""

    schema_version: str = Field(min_length=1)
    identity: ObservationAnalysisIdentity
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_payload_identity(self) -> ObservationAnalysisResultInput:
        if self.payload.get("schema_version") != self.schema_version:
            raise ValueError(
                "ObservationAnalysisResult payload schema_version does not match envelope"
            )
        payload_identity = self.payload.get("identity")
        if not isinstance(payload_identity, dict):
            raise ValueError("ObservationAnalysisResult payload must contain identity")
        if str(payload_identity.get("observation_id")) != str(self.identity.observation_id) or str(
            payload_identity.get("observation_run_id")
        ) != str(self.identity.observation_run_id):
            raise ValueError("ObservationAnalysisResult payload identity does not match envelope")
        return self


class ObservationReportInput(PersistenceModel):
    generated_at: datetime
    format: Literal["markdown"]
    content: str


def is_terminal_observation_run(status: ObservationRunStatus) -> bool:
    """Return whether an ObservationRun status cannot accept another transition."""

    return status in {
        ObservationRunStatus.COMPLETED,
        ObservationRunStatus.FAILED,
        ObservationRunStatus.CANCELLED,
    }


def is_terminal_lens_run(status: LensRunStatus) -> bool:
    """Return whether a LensRun status cannot accept another transition."""

    return status in {
        LensRunStatus.COMPLETED,
        LensRunStatus.PARTIAL,
        LensRunStatus.FAILED,
        LensRunStatus.CANCELLED,
    }


def is_usable_lens_result(status: LensRunStatus) -> bool:
    """Return whether a result status may be consumed as downstream analytical evidence."""

    return status in {LensRunStatus.COMPLETED, LensRunStatus.PARTIAL}


def validate_observation_run_transition(
    current: ObservationRunStatus,
    target: ObservationRunStatus,
    reason: StructuredReason | None = None,
) -> None:
    """Enforce forward ObservationRun transitions and required terminal reasons."""

    if current is ObservationRunStatus.PENDING and target is ObservationRunStatus.RUNNING:
        _validate_transition_reason(target, reason, requires_reason=False)
        return
    if current is ObservationRunStatus.RUNNING and target in {
        ObservationRunStatus.COMPLETED,
        ObservationRunStatus.FAILED,
        ObservationRunStatus.CANCELLED,
    }:
        _validate_transition_reason(
            target,
            reason,
            requires_reason=target in {ObservationRunStatus.FAILED, ObservationRunStatus.CANCELLED},
        )
        return
    raise ValueError(f"Invalid ObservationRun lifecycle transition: {current} -> {target}")


def validate_lens_run_transition(
    current: LensRunStatus,
    target: LensRunStatus,
    reason: StructuredReason | None = None,
) -> None:
    """Enforce forward LensRun transitions and required terminal reasons."""

    if current is LensRunStatus.PENDING and target is LensRunStatus.RUNNING:
        _validate_transition_reason(target, reason, requires_reason=False)
        return
    if (
        current in {LensRunStatus.PENDING, LensRunStatus.RUNNING}
        and target is LensRunStatus.CANCELLED
    ):
        _validate_transition_reason(target, reason, requires_reason=True)
        return
    if current is LensRunStatus.RUNNING and target in {
        LensRunStatus.COMPLETED,
        LensRunStatus.PARTIAL,
        LensRunStatus.FAILED,
    }:
        _validate_transition_reason(
            target,
            reason,
            requires_reason=target in {LensRunStatus.PARTIAL, LensRunStatus.FAILED},
        )
        return
    raise ValueError(f"Invalid LensRun lifecycle transition: {current} -> {target}")


def _validate_transition_reason(
    target: ObservationRunStatus | LensRunStatus,
    reason: StructuredReason | None,
    *,
    requires_reason: bool,
) -> None:
    """Keep lifecycle outcomes and structured reason metadata mutually consistent."""

    if requires_reason and reason is None:
        raise ValueError(f"{target.value} lifecycle transition requires a structured reason")
    if not requires_reason and reason is not None:
        raise ValueError(f"{target.value} lifecycle transition cannot include a structured reason")
    if target.value == "cancelled" and reason is not None:
        if reason.code != "execution_cancelled":
            raise ValueError(
                "cancelled lifecycle transition requires reason code execution_cancelled"
            )
        if reason.component is not None:
            raise ValueError("cancelled lifecycle transition cannot include a component")
