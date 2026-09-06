"""Framework-neutral ports used by Observation reasoning."""

# ruff: noqa: E501
from typing import Protocol

from app.knowledge.contracts import (
    KnowledgeRetrievalRequest,
    RetrievalAttempt,
    RetrievalOutcome,
)
from app.reasoning.contracts import (
    FindingCompletion,
    FindingRequest,
    HypothesisCompletion,
    HypothesisRequest,
    OverallStateCompletion,
    OverallStateRequest,
)


class ReasoningRetrievalSession(Protocol):
    """Expose the retrieval operations permitted to hypothesis reasoning."""

    @property
    def ledger(self) -> tuple[RetrievalAttempt, ...]:
        """Return metadata-only outcomes for this reasoning retrieval session."""

    async def execute(self, request: KnowledgeRetrievalRequest) -> RetrievalOutcome:
        """Submit one retrieval request under the session's reasoning policy."""


class ObservationReasoningAgent(Protocol):
    """Perform the three isolated Observation reasoning invocations."""

    async def form_findings(self, request: FindingRequest) -> FindingCompletion:
        """Return findings grounded only in supplied Observation evidence."""

    async def form_hypotheses(
        self, request: HypothesisRequest, retrieval: ReasoningRetrievalSession
    ) -> HypothesisCompletion:
        """Return hypotheses grounded in frozen findings and admitted knowledge."""

    async def determine_overall_state(self, request: OverallStateRequest) -> OverallStateCompletion:
        """Return the knowledge-isolated overall analytical state."""
