"""Focused contract and policy tests for bounded knowledge retrieval."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from app.knowledge.contracts import (
    KnowledgeReference,
    KnowledgeRetrievalRequest,
    RetrievalFailure,
    RetrievalRefinement,
    RetrievalRejected,
    RetrievalSuccess,
    RetrievalTimeout,
    RetrievedKnowledgeItem,
)
from app.knowledge.executor import BoundedRetrievalExecutor


def request(
    finding_ids: tuple[str, ...] = ("finding-1",), refinement: RetrievalRefinement | None = None
) -> KnowledgeRetrievalRequest:
    """Create one valid request without imposing consumer-specific subjects."""
    return KnowledgeRetrievalRequest(
        query="sentinel query", finding_ids=finding_ids, refinement=refinement
    )


class FakeRetriever:
    """Deterministic retriever fake for executor tests."""

    def __init__(self, result: object = ()) -> None:
        self.result = result
        self.calls: list[KnowledgeRetrievalRequest] = []

    async def retrieve(self, item: KnowledgeRetrievalRequest) -> tuple[RetrievedKnowledgeItem, ...]:
        """Record the request and return the configured test batch."""
        self.calls.append(item)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result  # type: ignore[return-value]


def test_contracts_are_strict_immutable_and_keep_opaque_references() -> None:
    reference = KnowledgeReference(source_id="manual:1", reference="section::odd/locator")
    item = RetrievedKnowledgeItem(statement="untrusted statement", references=(reference,))
    assert item.references[0].reference == "section::odd/locator"
    with pytest.raises(ValidationError):
        KnowledgeRetrievalRequest(query="", finding_ids=("finding-1",))
    with pytest.raises(ValidationError):
        KnowledgeReference(source_id="", reference="x")
    with pytest.raises(ValidationError):
        KnowledgeRetrievalRequest(query="x", finding_ids=("finding-1",), extra="forbidden")
    with pytest.raises(ValidationError):
        item.statement = "changed"  # type: ignore[misc]


@pytest.mark.anyio
async def test_retrieval_and_metadata_only_ledger() -> None:
    reference = KnowledgeReference(source_id="source-1", reference="ref-1")
    retriever = FakeRetriever(
        (RetrievedKnowledgeItem(statement="secret statement", references=(reference,)),)
    )
    executor = BoundedRetrievalExecutor(frozenset({"finding-1"}), retriever)
    outcome = await executor.execute(request())
    assert isinstance(outcome, RetrievalSuccess)
    assert outcome.items[0].statement == "secret statement"
    entry = executor.ledger[0]
    assert entry.model_dump() == {
        "submission_ordinal": 1,
        "execution_ordinal": 1,
        "supported_finding_ids": ("finding-1",),
        "refines_execution_ordinal": None,
        "executed": True,
        "consumed_slot": True,
        "outcome": "retrieved",
        "rejection_reason": None,
        "diagnostic_code": None,
        "knowledge_refs": ({"source_id": "source-1", "reference": "ref-1"},),
    }
    assert "secret statement" not in str(entry)


@pytest.mark.anyio
async def test_admission_precedence_refinement_and_budget() -> None:
    retriever = FakeRetriever()
    executor = BoundedRetrievalExecutor(frozenset({"finding-1"}), retriever)
    premature = await executor.execute(
        request(refinement=RetrievalRefinement(unresolved_gap="gap"))
    )
    assert (
        isinstance(premature, RetrievalRejected)
        and premature.rejection_reason == "invalid_refinement"
    )
    unknown = await executor.execute(
        request(("unknown",), RetrievalRefinement(unresolved_gap="gap"))
    )
    assert isinstance(unknown, RetrievalRejected) and unknown.rejection_reason == "unknown_finding"
    first = await executor.execute(request())
    second = await executor.execute(request(refinement=RetrievalRefinement(unresolved_gap="gap")))
    third = await executor.execute(request(("unknown",)))
    assert isinstance(first, RetrievalSuccess) and isinstance(second, RetrievalSuccess)
    assert isinstance(third, RetrievalRejected) and third.rejection_reason == "over_budget"
    assert [entry.execution_ordinal for entry in executor.ledger] == [None, None, 1, 2, None]
    assert executor.ledger[3].refines_execution_ordinal == 1


@pytest.mark.anyio
async def test_timeout_failure_and_invalid_results_consume_slots_without_disclosure() -> None:
    timeout = BoundedRetrievalExecutor(
        frozenset({"finding-1"}), FakeRetriever(TimeoutError("secret"))
    )
    timeout_outcome = await timeout.execute(request())
    assert isinstance(timeout_outcome, RetrievalTimeout)
    assert timeout_outcome.diagnostic_code == "retriever_timed_out"
    failure = BoundedRetrievalExecutor(
        frozenset({"finding-1"}), FakeRetriever(RuntimeError("credential"))
    )
    failure_outcome = await failure.execute(request())
    assert isinstance(failure_outcome, RetrievalFailure)
    assert failure_outcome.diagnostic_code == "retriever_failed" and "credential" not in str(
        failure.ledger
    )
    invalid = BoundedRetrievalExecutor(frozenset({"finding-1"}), FakeRetriever(["not a batch"]))
    invalid_outcome = await invalid.execute(request())
    assert isinstance(invalid_outcome, RetrievalFailure)
    assert invalid_outcome.diagnostic_code == "invalid_retriever_result"


@pytest.mark.anyio
async def test_concurrent_rejection_and_cancellation_leave_a_slot_and_ordinal_gap() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingRetriever:
        """Retriever fake whose in-flight call can be cancelled deterministically."""

        async def retrieve(
            self, item: KnowledgeRetrievalRequest
        ) -> tuple[RetrievedKnowledgeItem, ...]:
            """Wait until the test releases or cancels this call."""
            started.set()
            await release.wait()
            return ()

    executor = BoundedRetrievalExecutor(frozenset({"finding-1"}), BlockingRetriever())
    task = asyncio.create_task(executor.execute(request()))
    await started.wait()
    concurrent = await executor.execute(
        request(("unknown",), RetrievalRefinement(unresolved_gap="gap"))
    )
    assert isinstance(concurrent, RetrievalRejected) and concurrent.rejection_reason == "concurrent"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    later = await executor.execute(request())
    assert isinstance(later, RetrievalSuccess)
    assert executor.consumed_slots == 2
    assert [(entry.submission_ordinal, entry.execution_ordinal) for entry in executor.ledger] == [
        (2, None),
        (3, 2),
    ]
