"""Strict framework-neutral values for Observation report generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.reasoning.contracts import ObservationAnalysisResult, ObservationIdentity


class StrictReportingModel(BaseModel):
    """Immutable reporting value that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ReportSemanticContext(StrictReportingModel):
    """Minimal correlated semantic context admitted to report presentation."""

    identity: ObservationIdentity
    name: str = Field(min_length=1)
    description: str | None = None
    analytical_objective: str | None = None
    operational_context: str | None = None


class ReportAnalysisWindow(StrictReportingModel):
    """Exact UTC interval observed by the correlated immutable Observation run."""

    from_: datetime = Field(alias="from")
    to: datetime

    @field_validator("from_", "to")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        """Require exact UTC timestamps before report generation."""
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("report analysis window timestamps must be UTC")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_forward_window(self) -> ReportAnalysisWindow:
        """Reject empty and backward report observation intervals."""
        if self.from_ >= self.to:
            raise ValueError("report analysis window must be forward")
        return self


class ReportGenerationRequest(StrictReportingModel):
    """Combine one analysis result with its minimal report context."""

    context: ReportSemanticContext
    analysis_result: ObservationAnalysisResult
    analysis_window: ReportAnalysisWindow


class FindingPresentation(StrictReportingModel):
    """English presentation text keyed to one source finding."""

    finding_id: str = Field(min_length=1)
    heading: str | None = None
    presentation: str = Field(min_length=1)


class HypothesisPresentation(StrictReportingModel):
    """English presentation text keyed to one source hypothesis."""

    hypothesis_id: str = Field(min_length=1)
    presentation: str = Field(min_length=1)


class LimitationPresentation(StrictReportingModel):
    """English presentation text keyed to one source limitation position."""

    limitation_index: int = Field(ge=0)
    presentation: str = Field(min_length=1)


class ReportPresentationDraft(StrictReportingModel):
    """Structured presentation completion before deterministic Markdown rendering."""

    overall_state: Literal["no_significant_findings", "significant_findings_present", "uncertain"]
    overall_assessment: str = Field(min_length=1)
    objective_summary: str | None = None
    findings: tuple[FindingPresentation, ...] = ()
    hypotheses: tuple[HypothesisPresentation, ...] = ()
    limitations: tuple[LimitationPresentation, ...] = ()


class ObservationReport(StrictReportingModel):
    """Minimal immutable Markdown presentation artifact for one Observation run."""

    observation_id: UUID
    observation_run_id: UUID
    generated_at: datetime
    format: Literal["markdown"] = "markdown"
    content: str = Field(min_length=1)

    @field_validator("generated_at")
    @classmethod
    def generated_at_is_utc(cls, value: datetime) -> datetime:
        """Require an aware UTC timestamp supplied by the application clock."""
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("generated_at must be UTC")
        return value.astimezone(UTC)

    @field_validator("content")
    @classmethod
    def non_blank_content(cls, value: str) -> str:
        """Reject an empty or whitespace-only Markdown artifact."""
        if not value.strip():
            raise ValueError("report content must not be blank")
        return value


class ReportSuccess(StrictReportingModel):
    """Successful in-memory report generation outcome."""

    outcome: Literal["success"] = "success"
    report: ObservationReport


class ReportFailure(StrictReportingModel):
    """Safe fail-closed report outcome without diagnostics or partial content."""

    outcome: Literal["failure"] = "failure"
    code: Literal[
        "report_model_failed",
        "report_model_timed_out",
        "report_policy_violated",
        "report_result_invalid",
    ]
    component: Literal["request_validation", "report_generation", "report_builder"]


ReportGenerationOutcome = Annotated[ReportSuccess | ReportFailure, Field(discriminator="outcome")]


class ReportPolicyViolation(ValueError):
    """Internal signal that the presentation-only execution policy was violated."""
