"""Framework-neutral ports used by Observation reasoning."""

# ruff: noqa: E501
from typing import Protocol

from app.knowledge.executor import BoundedRetrievalExecutor
from app.reasoning.contracts import (
    FindingCompletion,
    FindingRequest,
    HypothesisCompletion,
    HypothesisRequest,
    OverallStateCompletion,
    OverallStateRequest,
)


class ObservationReasoningAgent(Protocol):
    """Perform the three isolated Observation reasoning invocations."""

    async def form_findings(self, request: FindingRequest) -> FindingCompletion:
        """Return findings grounded only in supplied Observation evidence."""

    async def form_hypotheses(
        self, request: HypothesisRequest, retrieval: BoundedRetrievalExecutor
    ) -> HypothesisCompletion:
        """Return hypotheses grounded in frozen findings and admitted knowledge."""

    async def determine_overall_state(self, request: OverallStateRequest) -> OverallStateCompletion:
        """Return the knowledge-isolated overall analytical state."""
