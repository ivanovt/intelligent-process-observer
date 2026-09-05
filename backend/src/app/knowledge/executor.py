"""Deterministic run-scoped execution policy for knowledge retrieval."""

from __future__ import annotations

import asyncio

from app.knowledge.contracts import (
    KnowledgeReference,
    KnowledgeRetrievalRequest,
    RetrievalAttempt,
    RetrievalFailure,
    RetrievalOutcome,
    RetrievalRejected,
    RetrievalSuccess,
    RetrievalTimeout,
    RetrievedKnowledgeItem,
)
from app.knowledge.ports import KnowledgeRetriever


class BoundedRetrievalExecutor:
    """Enforce finding grounding and a sequential two-call retrieval budget per run."""

    def __init__(self, frozen_finding_ids: frozenset[str], retriever: KnowledgeRetriever) -> None:
        """Bind this executor to one non-empty immutable finding scope and retriever."""
        if not frozen_finding_ids or any(not finding_id for finding_id in frozen_finding_ids):
            raise ValueError("frozen_finding_ids must be a non-empty set of non-empty values")
        self._frozen_finding_ids = frozenset(frozen_finding_ids)
        self._retriever = retriever
        self._lock = asyncio.Lock()
        self._next_submission_ordinal = 1
        self._consumed_slots = 0
        self._active = False
        self._attempts: dict[int, RetrievalAttempt] = {}

    @property
    def ledger(self) -> tuple[RetrievalAttempt, ...]:
        """Return an immutable, submission-ordered snapshot of typed outcomes."""
        return tuple(self._attempts[ordinal] for ordinal in sorted(self._attempts))

    @property
    def consumed_slots(self) -> int:
        """Return the number of retrieval slots irrevocably consumed in this session."""
        return self._consumed_slots

    async def execute(self, request: KnowledgeRetrievalRequest) -> RetrievalOutcome:
        """Admit and execute one grounded request under the fixed session policy."""
        async with self._lock:
            submission_ordinal = self._next_submission_ordinal
            self._next_submission_ordinal += 1
            rejection = self._rejection_reason(request)
            if rejection is not None:
                outcome = RetrievalRejected(rejection_reason=rejection)
                self._record_rejection(submission_ordinal, request, outcome)
                return outcome
            self._active = True
            self._consumed_slots += 1
            execution_ordinal = self._consumed_slots

        try:
            outcome = await self._retrieve(request)
        except asyncio.CancelledError:
            # A cancellation has no typed outcome and therefore no ledger entry.
            await self._release_active()
            raise

        attempt = RetrievalAttempt(
            submission_ordinal=submission_ordinal,
            execution_ordinal=execution_ordinal,  # execution ordinals are bounded by admission.
            supported_finding_ids=request.finding_ids,
            refines_execution_ordinal=1 if request.refinement is not None else None,
            executed=True,
            consumed_slot=True,
            outcome=outcome.outcome,
            diagnostic_code=getattr(outcome, "diagnostic_code", None),
            knowledge_refs=_references(outcome),
        )
        async with self._lock:
            self._attempts[submission_ordinal] = attempt
            self._active = False
        return outcome

    def _rejection_reason(self, request: KnowledgeRetrievalRequest) -> str | None:
        if self._consumed_slots >= 2:
            return "over_budget"
        if self._active:
            return "concurrent"
        if not set(request.finding_ids).issubset(self._frozen_finding_ids):
            return "unknown_finding"
        if request.refinement is not None and self._consumed_slots != 1:
            return "invalid_refinement"
        return None

    def _record_rejection(
        self,
        submission_ordinal: int,
        request: KnowledgeRetrievalRequest,
        outcome: RetrievalRejected,
    ) -> None:
        self._attempts[submission_ordinal] = RetrievalAttempt(
            submission_ordinal=submission_ordinal,
            supported_finding_ids=request.finding_ids,
            refines_execution_ordinal=None,
            executed=False,
            consumed_slot=False,
            outcome=outcome.outcome,
            rejection_reason=outcome.rejection_reason,
        )

    async def _retrieve(self, request: KnowledgeRetrievalRequest) -> RetrievalOutcome:
        try:
            items = await self._retriever.retrieve(request)
        except TimeoutError:
            return RetrievalTimeout()
        except asyncio.CancelledError:
            raise
        except Exception:
            return RetrievalFailure(diagnostic_code="retriever_failed")
        if not _valid_batch(items):
            return RetrievalFailure(diagnostic_code="invalid_retriever_result")
        return RetrievalSuccess(items=items)

    async def _release_active(self) -> None:
        """Release the run-local active guard after caller cancellation."""
        async with self._lock:
            self._active = False


def _valid_batch(items: object) -> bool:
    return isinstance(items, tuple) and all(
        isinstance(item, RetrievedKnowledgeItem) for item in items
    )


def _references(outcome: RetrievalOutcome) -> tuple[KnowledgeReference, ...]:
    if not isinstance(outcome, RetrievalSuccess):
        return ()
    return tuple(reference for item in outcome.items for reference in item.references)
