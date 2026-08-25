"""Framework-neutral input, output, and trace contracts for the experiment."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenContract(BaseModel):
    """Immutable experiment data; external framework objects never cross this boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class LensContext(FrozenContract):
    scope_description: str
    current_window: str
    reference_window: str


class AlertRecord(FrozenContract):
    alert_id: str
    status: Literal["active", "acknowledged", "resolved"]
    occurrence_count: int = Field(ge=1)
    duration_seconds: float | None = Field(default=None, ge=0)
    provider_importance: Literal["low", "moderate", "high", "critical"]


class AlertActivity(FrozenContract):
    current_count: int = Field(ge=1)
    reference_count: int = Field(ge=0)


class StatusDistribution(FrozenContract):
    active: int = Field(ge=0)
    acknowledged: int = Field(ge=0)
    resolved: int = Field(ge=0)


class ProviderImportanceDistribution(FrozenContract):
    low: int = Field(ge=0)
    moderate: int = Field(ge=0)
    high: int = Field(ge=0)
    critical: int = Field(ge=0)


class ReferenceOccurrenceComparison(FrozenContract):
    alert_id: str
    direction: Literal["increased", "decreased", "unchanged"]
    current_occurrences: int = Field(ge=0)
    reference_occurrences: int = Field(ge=0)


class AlertAnalysisInput(FrozenContract):
    """The immutable, already-fetched Alert Lens input available to both agents."""

    lens_context: LensContext
    alerts: tuple[AlertRecord, ...]
    activity: AlertActivity
    status_distribution: StatusDistribution
    provider_importance_distribution: ProviderImportanceDistribution
    reference_occurrence_comparisons: tuple[ReferenceOccurrenceComparison, ...] = ()


class ToolExecutionResult(FrozenContract):
    status: Literal["success", "not_applicable", "failed", "timeout"]
    data: dict | None = None


class AlertFinding(FrozenContract):
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)


class AlertAnalysisAgentOutput(FrozenContract):
    """The agent-only portion used by the deterministic result builder in production."""

    findings: tuple[AlertFinding, ...] = ()
    overall_importance: Literal["low", "moderate", "high", "critical"]


class ToolAttemptTrace(FrozenContract):
    invocation_order: int = Field(ge=1)
    tool_name: str
    status: Literal["success", "not_applicable", "failed", "timeout"]
    latency_ms: float = Field(ge=0)


class AgentRunResult(FrozenContract):
    output: AlertAnalysisAgentOutput
    tool_attempts: tuple[ToolAttemptTrace, ...]
    available_evidence_ids: tuple[str, ...]
    blocked_tool_calls: int = Field(default=0, ge=0)


class ExperimentSettings(FrozenContract):
    """Fixed, final OpenRouter/Terra configuration for framework comparison only."""

    provider_api: Literal["openrouter_chat_completions"] = "openrouter_chat_completions"
    model: Literal["openai/gpt-5.6-terra"] = "openai/gpt-5.6-terra"
    base_url: str = "https://openrouter.ai/api/v1"
    provider_order: tuple[Literal["openai"], ...] = ("openai",)
    allow_provider_fallbacks: bool = False
    reasoning_effort: Literal["medium"] = "medium"
    max_output_tokens: int = Field(default=2_000, ge=1)
    model_timeout_seconds: float = Field(default=60.0, gt=0)
    analytical_tool_timeout_seconds: float = Field(default=1.0, gt=0)
    parallel_tool_calls: bool = False
    provider_retries: int = Field(default=0, ge=0)
    framework_retries: int = Field(default=0, ge=0)
