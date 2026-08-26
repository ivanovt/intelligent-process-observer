"""Experiment-local deterministic retrieval, with a framework-neutral two-call boundary."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Literal

from pydantic import Field

from agent_framework_experiment.observation_reasoning.domain import FrozenModel, KnowledgeReference
from agent_framework_experiment.observation_reasoning.phase import FrozenFindingsState


class KnowledgeItem(FrozenModel):
    statement: str
    knowledge_ref: KnowledgeReference


class KnowledgeRetrievalRequest(FrozenModel):
    query: str = Field(min_length=1)
    supported_finding_ids: tuple[str, ...] = Field(min_length=1)
    refines_attempt: int | None = None
    unresolved_gap: str | None = None


class KnowledgeRetrievalResult(FrozenModel):
    status: Literal["success", "insufficient", "no_match", "failed", "timeout"]
    knowledge: tuple[KnowledgeItem, ...] = ()


class RetrievalTrace(FrozenModel):
    attempt_order: int
    executed: bool
    query: str
    supported_finding_ids: tuple[str, ...]
    status: Literal["success", "insufficient", "no_match", "failed", "timeout", "blocked"]
    knowledge_refs: tuple[KnowledgeReference, ...] = ()
    refines_attempt: int | None = None
    unresolved_gap: str | None = None
    latency_ms: float = 0


Retriever = Callable[
    [KnowledgeRetrievalRequest], KnowledgeRetrievalResult | Awaitable[KnowledgeRetrievalResult]
]


class RetrievalExecutor:
    """Experiment-local semantics: insufficient is refine-only, not hypothesis grounding."""

    def __init__(
        self,
        frozen: FrozenFindingsState | None = None,
        *,
        timeout_seconds: float = 1.0,
        retriever: Retriever,
    ) -> None:
        self.frozen = frozen
        self.timeout_seconds = timeout_seconds
        self.retriever = retriever
        self._traces: list[RetrievalTrace] = []
        self._successful_refs: set[KnowledgeReference] = set()
        self._refinement_refs: set[KnowledgeReference] = set()

    @property
    def traces(self) -> tuple[RetrievalTrace, ...]:
        return tuple(self._traces)

    def set_frozen_findings(self, frozen: FrozenFindingsState) -> None:
        if self.frozen is not None:
            raise RuntimeError("findings are already frozen for this retrieval executor")
        self.frozen = frozen

    @property
    def available_hypothesis_refs(self) -> tuple[KnowledgeReference, ...]:
        return tuple(
            sorted(self._successful_refs, key=lambda item: (item.source_id, item.reference))
        )

    @property
    def available_refinement_refs(self) -> tuple[KnowledgeReference, ...]:
        return tuple(
            sorted(self._refinement_refs, key=lambda item: (item.source_id, item.reference))
        )

    async def invoke(
        self, request: KnowledgeRetrievalRequest
    ) -> KnowledgeRetrievalResult | dict[str, str]:
        trace_order = len(self._traces) + 1
        executed_attempts = sum(trace.executed for trace in self._traces)
        if self.frozen is None:
            self._traces.append(
                RetrievalTrace(
                    attempt_order=trace_order,
                    executed=False,
                    query=request.query,
                    supported_finding_ids=request.supported_finding_ids,
                    status="blocked",
                )
            )
            return {"status": "blocked", "reason": "findings_not_frozen"}
        if not set(request.supported_finding_ids) <= set(self.frozen.finding_ids):
            raise ValueError("retrieval query must cite frozen finding IDs only")
        if executed_attempts >= 2:
            self._traces.append(
                RetrievalTrace(
                    attempt_order=trace_order,
                    executed=False,
                    query=request.query,
                    supported_finding_ids=request.supported_finding_ids,
                    status="blocked",
                )
            )
            return {"status": "blocked", "reason": "retrieval_budget_exhausted"}
        if request.refines_attempt is not None:
            if request.refines_attempt != 1 or executed_attempts != 1 or not request.unresolved_gap:
                raise ValueError(
                    "a refinement must reference successful/insufficient attempt 1 and a gap"
                )
            first = next((trace for trace in self._traces if trace.executed), None)
            if first is None or first.status not in {"success", "insufficient"}:
                raise ValueError("refinement requires useful first retrieval context")
        started = perf_counter()
        try:
            candidate = self.retriever(request)
            result = await candidate if isinstance(candidate, Awaitable) else candidate
        except TimeoutError:
            result = KnowledgeRetrievalResult(status="timeout")
        except Exception:
            result = KnowledgeRetrievalResult(status="failed")
        if result.status in {"no_match", "failed", "timeout"} and result.knowledge:
            raise ValueError(f"{result.status} cannot expose usable knowledge")
        refs = tuple(item.knowledge_ref for item in result.knowledge)
        if result.status == "success":
            self._successful_refs.update(refs)
            self._refinement_refs.update(refs)
        elif result.status == "insufficient":
            self._refinement_refs.update(refs)
        self._traces.append(
            RetrievalTrace(
                attempt_order=trace_order,
                executed=True,
                query=request.query,
                supported_finding_ids=request.supported_finding_ids,
                status=result.status,
                knowledge_refs=refs,
                refines_attempt=request.refines_attempt,
                unresolved_gap=request.unresolved_gap,
                latency_ms=(perf_counter() - started) * 1_000,
            )
        )
        return result
