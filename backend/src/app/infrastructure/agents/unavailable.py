"""Safe framework-neutral agent ports used without configured model access."""

from __future__ import annotations

from app.alerts.contracts import AlertAgentCompletion, AlertAgentRequest
from app.alerts.ports import AlertOptionalToolExecutor
from app.metrics.contracts import (
    MetricAgentOperationalFailure,
    MetricAgentOutcome,
    MetricAgentRequest,
)
from app.metrics.ports import MetricToolExecutor
from app.reasoning.contracts import (
    FindingCompletion,
    FindingRequest,
    HypothesisCompletion,
    HypothesisRequest,
    OverallStateCompletion,
    OverallStateRequest,
)
from app.reasoning.ports import ReasoningRetrievalSession
from app.reporting.contracts import ReportGenerationRequest, ReportPresentationDraft


class UnavailableMetricsAnalysisAgent:
    """Return the existing safe Metric agent failure when model access is unavailable."""

    async def complete(
        self, request: MetricAgentRequest, tools: MetricToolExecutor | None = None
    ) -> MetricAgentOutcome:
        """Return a non-diagnostic operational failure without calling a provider."""
        return MetricAgentOperationalFailure()


class UnavailableAlertAnalysisAgent:
    """Fail the Alert port safely when production model access is unavailable."""

    async def complete(
        self, request: AlertAgentRequest, tools: AlertOptionalToolExecutor
    ) -> AlertAgentCompletion:
        """Raise a generic failure mapped by the existing Alert pipeline."""
        raise RuntimeError("model access unavailable")


class UnavailableObservationReasoningAgent:
    """Fail each reasoning phase safely when production model access is unavailable."""

    async def form_findings(self, request: FindingRequest) -> FindingCompletion:
        """Raise a generic failure mapped by the reasoning executor."""
        raise RuntimeError("model access unavailable")

    async def form_hypotheses(
        self, request: HypothesisRequest, retrieval: ReasoningRetrievalSession
    ) -> HypothesisCompletion:
        """Raise a generic failure mapped by the reasoning executor."""
        raise RuntimeError("model access unavailable")

    async def determine_overall_state(self, request: OverallStateRequest) -> OverallStateCompletion:
        """Raise a generic failure mapped by the reasoning executor."""
        raise RuntimeError("model access unavailable")


class UnavailableReportGenerationAgent:
    """Fail report presentation safely when production model access is unavailable."""

    async def complete_presentation(
        self, request: ReportGenerationRequest
    ) -> ReportPresentationDraft:
        """Raise a generic failure mapped by the report executor."""
        raise RuntimeError("model access unavailable")
