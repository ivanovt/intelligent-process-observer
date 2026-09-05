"""Strict contracts for source-agnostic knowledge retrieval."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictKnowledgeModel(BaseModel):
    """Base model that rejects unknown retrieval-contract fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class KnowledgeReference(StrictKnowledgeModel):
    """Opaque provenance reference for one retrieved knowledge statement."""

    source_id: str = Field(min_length=1)
    reference: str = Field(min_length=1)


class RetrievedKnowledgeItem(StrictKnowledgeModel):
    """Untrusted retrieved statement with its associated provenance references."""

    statement: str = Field(min_length=1)
    references: tuple[KnowledgeReference, ...] = Field(min_length=1)


class RetrievalRefinement(StrictKnowledgeModel):
    """Caller-declared unresolved gap for a possible second retrieval call."""

    unresolved_gap: str = Field(min_length=1)


class KnowledgeRetrievalRequest(StrictKnowledgeModel):
    """Query grounded in one or more already-frozen finding identifiers."""

    query: str = Field(min_length=1)
    finding_ids: tuple[str, ...] = Field(min_length=1)
    refinement: RetrievalRefinement | None = None

    @model_validator(mode="after")
    def validate_finding_ids(self) -> KnowledgeRetrievalRequest:
        """Require non-empty, unique finding identifiers."""
        if any(not finding_id for finding_id in self.finding_ids):
            raise ValueError("finding_ids must contain only non-empty values")
        if len(self.finding_ids) != len(set(self.finding_ids)):
            raise ValueError("finding_ids must be unique")
        return self


class RetrievalSuccess(StrictKnowledgeModel):
    """Successful retrieval, including the valid empty-result case."""

    outcome: Literal["retrieved"] = "retrieved"
    items: tuple[RetrievedKnowledgeItem, ...] = ()


class RetrievalFailure(StrictKnowledgeModel):
    """Safe failure outcome without retriever diagnostic detail."""

    outcome: Literal["failed"] = "failed"
    diagnostic_code: Literal["retriever_failed", "invalid_retriever_result"]


class RetrievalTimeout(StrictKnowledgeModel):
    """Safe timeout outcome without retriever diagnostic detail."""

    outcome: Literal["timed_out"] = "timed_out"
    diagnostic_code: Literal["retriever_timed_out"] = "retriever_timed_out"


class RetrievalRejected(StrictKnowledgeModel):
    """Deterministic admission rejection without retriever execution."""

    outcome: Literal["rejected"] = "rejected"
    rejection_reason: Literal["over_budget", "concurrent", "unknown_finding", "invalid_refinement"]


RetrievalOutcome = RetrievalSuccess | RetrievalFailure | RetrievalTimeout | RetrievalRejected


class RetrievalAttempt(StrictKnowledgeModel):
    """Metadata-only transient record of one completed retrieval submission."""

    submission_ordinal: int = Field(gt=0)
    execution_ordinal: Literal[1, 2] | None = None
    supported_finding_ids: tuple[str, ...] = Field(min_length=1)
    refines_execution_ordinal: Literal[1] | None = None
    executed: bool
    consumed_slot: bool
    outcome: Literal["retrieved", "failed", "timed_out", "rejected"]
    rejection_reason: (
        Literal["over_budget", "concurrent", "unknown_finding", "invalid_refinement"] | None
    ) = None
    diagnostic_code: (
        Literal["retriever_timed_out", "retriever_failed", "invalid_retriever_result"] | None
    ) = None
    knowledge_refs: tuple[KnowledgeReference, ...] = ()

    @model_validator(mode="after")
    def validate_projection(self) -> RetrievalAttempt:
        """Enforce the ledger's outcome-specific metadata projection."""
        if any(not finding_id for finding_id in self.supported_finding_ids):
            raise ValueError("supported_finding_ids must contain only non-empty values")
        if self.executed != self.consumed_slot:
            raise ValueError("executed and consumed_slot must have the same value")
        if self.executed != (self.execution_ordinal is not None):
            raise ValueError("execution_ordinal must be present exactly for executed attempts")
        if self.refines_execution_ordinal is not None and self.execution_ordinal != 2:
            raise ValueError("only execution ordinal 2 may refine execution ordinal 1")
        if self.outcome == "rejected":
            if self.executed or self.rejection_reason is None or self.diagnostic_code is not None:
                raise ValueError("rejected attempts must contain only a rejection reason")
            if self.knowledge_refs:
                raise ValueError("rejected attempts must not contain knowledge references")
        else:
            if not self.executed or self.rejection_reason is not None:
                raise ValueError("executed attempts must not contain a rejection reason")
            if self.outcome == "retrieved":
                if self.diagnostic_code is not None:
                    raise ValueError("retrieved attempts must not contain a diagnostic code")
            elif self.diagnostic_code is None:
                raise ValueError("failed and timed-out attempts require a diagnostic code")
            elif self.knowledge_refs:
                raise ValueError(
                    "failed and timed-out attempts must not contain knowledge references"
                )
        return self
