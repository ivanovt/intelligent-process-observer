"""Framework-neutral contracts for the Observation Reasoning experiment."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Identity(FrozenModel):
    observation_id: str
    observation_run_id: str


class EvidenceItem(FrozenModel):
    evidence_id: str
    statement: str


class UnavailableLens(FrozenModel):
    lens_id: str
    lens_type: str
    reason_code: str


class KnowledgeReference(FrozenModel):
    source_id: str
    reference: str


class UpstreamKnowledge(FrozenModel):
    id: str
    statement: str
    knowledge_refs: tuple[KnowledgeReference, ...]


class ObservationReasoningInput(FrozenModel):
    identity: Identity
    context_description: str
    usable_evidence: tuple[EvidenceItem, ...]
    relationship_evidence: tuple[EvidenceItem, ...] = ()
    unavailable_lenses: tuple[UnavailableLens, ...] = ()
    upstream_log_knowledge: tuple[UpstreamKnowledge, ...] = ()


class Finding(FrozenModel):
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class Limitation(FrozenModel):
    code: str
    lens_id: str
    component: str | None = None


class Hypothesis(FrozenModel):
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    supported_by: tuple[str, ...] = Field(min_length=1)
    knowledge_refs: tuple[KnowledgeReference, ...] = Field(min_length=1)


class FindingFormationOutput(FrozenModel):
    findings: tuple[Finding, ...] = ()
    overall_state: Literal["no_significant_findings", "significant_findings_present", "uncertain"]
    limitations: tuple[Limitation, ...] = ()


class HypothesisFormationOutput(FrozenModel):
    hypotheses: tuple[Hypothesis, ...] = ()


class ObservationAnalysisResult(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    identity: Identity
    overall_state: Literal["no_significant_findings", "significant_findings_present", "uncertain"]
    findings: tuple[Finding, ...] = ()
    hypotheses: tuple[Hypothesis, ...] = ()
    limitations: tuple[Limitation, ...] = ()


class ReasoningSettings(FrozenModel):
    provider_api: Literal["openrouter_chat_completions"] = "openrouter_chat_completions"
    model: Literal["openai/gpt-5.6-terra"] = "openai/gpt-5.6-terra"
    base_url: str = "https://openrouter.ai/api/v1"
    provider_order: tuple[Literal["openai"], ...] = ("openai",)
    allow_provider_fallbacks: bool = False
    reasoning_effort: Literal["medium"] = "medium"
    max_output_tokens: int = 2_000
    model_timeout_seconds: float = 60.0
    retrieval_timeout_seconds: float = 1.0
    parallel_tool_calls: bool = False
    provider_retries: int = 0
    framework_retries: int = 0
