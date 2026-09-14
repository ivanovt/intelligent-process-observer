"""Strict framework-neutral contracts for Observation reasoning."""
# ruff: noqa: E501

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.alerts.contracts import CompletedAlertAnalysisResult, PartialAlertAnalysisResult
from app.infrastructure.persistence.runtime_contracts import StructuredReason
from app.knowledge.contracts import KnowledgeReference
from app.metrics.contracts import CompletedSufficientMetricResult, PartialMetricResult
from app.relationships.contracts import RelationshipEvaluation


class StrictReasoningModel(BaseModel):
    """Immutable reasoning value that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ObservationIdentity(StrictReasoningModel):
    """Correlates one reasoning result to an Observation execution."""

    observation_id: UUID
    observation_run_id: UUID


class ReasoningLens(StrictReasoningModel):
    """Compact semantic description of one configured Lens."""

    lens_id: str = Field(min_length=1)
    lens_type: Literal["metric", "alert", "log"]
    name: str = Field(min_length=1)
    description: str | None = None
    analysis_objectives: tuple[str, ...] = ()


class ObservationSemanticContext(StrictReasoningModel):
    """LLM-safe semantic projection of an Observation definition."""

    identity: ObservationIdentity
    name: str = Field(min_length=1)
    description: str | None = None
    analytical_objective: str | None = None
    operational_context: str | None = None
    lenses: tuple[ReasoningLens, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_lenses(self) -> ObservationSemanticContext:
        if len({(lens.lens_type, lens.lens_id) for lens in self.lenses}) != len(self.lenses):
            raise ValueError("semantic context Lens identities must be unique")
        return self


class UnavailableReasonSnapshot(StrictReasoningModel):
    """Immutable code-and-component snapshot for unavailable Lens metadata."""

    code: str = Field(min_length=1)
    component: str | None = None


class UnavailableLens(StrictReasoningModel):
    """A configured Lens without usable analytical evidence."""

    lens_id: str = Field(min_length=1)
    lens_type: Literal["metric", "alert"]
    origin: Literal["caller_unavailable", "completed_insufficient_metric"]
    reason: UnavailableReasonSnapshot

    @field_validator("reason", mode="before")
    @classmethod
    def snapshot_persistence_reason(cls, value: object) -> object:
        """Copy mutable persistence reasons across the reasoning contract boundary."""
        if isinstance(value, StructuredReason):
            return {"code": value.code, "component": value.component}
        return value

    @model_validator(mode="after")
    def validate_origin_reason(self) -> UnavailableLens:
        """Restrict the deterministic insufficient-Metric unavailable value."""
        if self.origin == "completed_insufficient_metric" and (
            self.lens_type != "metric"
            or self.reason.code != "insufficient_data"
            or self.reason.component is not None
        ):
            raise ValueError(
                "completed insufficient Metric unavailability requires metric "
                "insufficient_data without a component"
            )
        return self


UsableLensResult = (
    CompletedSufficientMetricResult
    | PartialMetricResult
    | CompletedAlertAnalysisResult
    | PartialAlertAnalysisResult
)


class ObservationReasoningInput(StrictReasoningModel):
    """Correlated native evidence admitted to Observation reasoning."""

    context: ObservationSemanticContext
    usable_results: tuple[UsableLensResult, ...] = ()
    unavailable_lenses: tuple[UnavailableLens, ...] = ()
    relationships: tuple[RelationshipEvaluation, ...] = ()


class EvidenceReference(StrictReasoningModel):
    """Stable reference to a retained element of an immutable source artifact."""

    source_type: Literal["metric_result", "alert_result", "relationship_evaluation"]
    source_id: UUID | str
    locator: tuple[str | int, ...] = Field(min_length=1)

    @field_validator("locator")
    @classmethod
    def valid_locator(cls, value: tuple[str | int, ...]) -> tuple[str | int, ...]:
        if any(
            (isinstance(item, str) and not item) or (isinstance(item, int) and item < 0)
            for item in value
        ):
            raise ValueError("locator values must be non-empty keys or non-negative indexes")
        return value


class EvidenceCatalogEntry(StrictReasoningModel):
    """Transient deterministic ID paired with a stable evidence reference."""

    id: str = Field(pattern=r"^evidence_[0-9]{4}$")
    reference: EvidenceReference


class FindingDraft(StrictReasoningModel):
    """Model-authored finding before catalog references are frozen."""

    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class FindingCompletion(StrictReasoningModel):
    """Evidence-only finding phase output."""

    findings: tuple[FindingDraft, ...] = ()


class Finding(StrictReasoningModel):
    """Frozen Observation finding grounded in structured evidence."""

    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_refs: tuple[EvidenceReference, ...] = Field(min_length=1)


class Hypothesis(StrictReasoningModel):
    """Knowledge-grounded explanatory hypothesis."""

    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    supported_by: tuple[str, ...] = Field(min_length=1)
    knowledge_refs: tuple[KnowledgeReference, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_references(self) -> Hypothesis:
        if len(self.supported_by) != len(set(self.supported_by)) or len(self.knowledge_refs) != len(
            set(self.knowledge_refs)
        ):
            raise ValueError("hypothesis references must be unique")
        return self


class HypothesisCompletion(StrictReasoningModel):
    """Knowledge-enabled hypothesis phase output."""

    hypotheses: tuple[Hypothesis, ...] = ()


class LimitationBase(StrictReasoningModel):
    """Deterministic availability constraint on Observation evidence."""

    lens_id: str = Field(min_length=1)
    lens_type: Literal["metric", "alert"]


class MissingLensEvidence(LimitationBase):
    code: Literal["missing_lens_evidence"] = "missing_lens_evidence"


class InsufficientLensEvidence(LimitationBase):
    code: Literal["insufficient_lens_evidence"] = "insufficient_lens_evidence"


class PartialLensAnalysis(LimitationBase):
    code: Literal["partial_lens_analysis"] = "partial_lens_analysis"
    component: str | None = None


Limitation = Annotated[
    MissingLensEvidence | InsufficientLensEvidence | PartialLensAnalysis,
    Field(discriminator="code"),
]


class FindingRequest(StrictReasoningModel):
    """Evidence-only input to the finding invocation."""

    context: ObservationSemanticContext
    usable_results: tuple[UsableLensResult, ...]
    relationships: tuple[RelationshipEvaluation, ...]
    catalog: tuple[EvidenceCatalogEntry, ...]
    limitations: tuple[Limitation, ...]


class HypothesisRequest(StrictReasoningModel):
    """Frozen-finding input to the optional hypothesis invocation."""

    context: ObservationSemanticContext
    usable_results: tuple[UsableLensResult, ...]
    relationships: tuple[RelationshipEvaluation, ...]
    catalog: tuple[EvidenceCatalogEntry, ...]
    findings: tuple[Finding, ...]
    limitations: tuple[Limitation, ...]


class OverallStateRequest(StrictReasoningModel):
    """Knowledge-isolated evidence input to overall-state determination."""

    context: ObservationSemanticContext
    usable_results: tuple[UsableLensResult, ...]
    relationships: tuple[RelationshipEvaluation, ...]
    catalog: tuple[EvidenceCatalogEntry, ...]
    findings: tuple[Finding, ...]
    limitations: tuple[Limitation, ...]


class OverallStateCompletion(StrictReasoningModel):
    """The only output authored by overall-state determination."""

    overall_state: Literal["no_significant_findings", "significant_findings_present", "uncertain"]


class ObservationAnalysisResult(StrictReasoningModel):
    """Strict final in-memory Observation reasoning artifact."""

    schema_version: Literal["1.0"] = "1.0"
    identity: ObservationIdentity
    overall_state: Literal["no_significant_findings", "significant_findings_present", "uncertain"]
    findings: tuple[Finding, ...]
    hypotheses: tuple[Hypothesis, ...]
    limitations: tuple[Limitation, ...]


class ReasoningSuccess(StrictReasoningModel):
    """Successful in-memory reasoning outcome."""

    outcome: Literal["success"] = "success"
    result: ObservationAnalysisResult


class ReasoningFailure(StrictReasoningModel):
    """Safe fail-closed reasoning outcome without diagnostics."""

    outcome: Literal["failure"] = "failure"
    code: Literal[
        "reasoning_model_failed",
        "reasoning_model_timed_out",
        "reasoning_policy_violated",
        "reasoning_result_invalid",
    ]
    component: Literal["finding_phase", "hypothesis_phase", "overall_state_phase", "result_builder"]


ReasoningOutcome = Annotated[ReasoningSuccess | ReasoningFailure, Field(discriminator="outcome")]


class ReasoningPolicyViolation(ValueError):
    """Internal signal that a bounded reasoning policy was violated."""
