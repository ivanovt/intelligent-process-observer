"""Deterministic three-phase Observation reasoning orchestration."""

# ruff: noqa: E501
from __future__ import annotations

import asyncio

from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded

from app.knowledge.contracts import KnowledgeRetrievalRequest, RetrievalOutcome, RetrievalRejected
from app.knowledge.executor import BoundedRetrievalExecutor
from app.knowledge.ports import KnowledgeRetriever
from app.reasoning.builder import build_result, freeze_findings, validate_hypotheses
from app.reasoning.catalog import build_catalog
from app.reasoning.contracts import (
    ReasoningFailure,
    ReasoningOutcome,
    ReasoningPolicyViolation,
    ReasoningSuccess,
)
from app.reasoning.input import derive_limitations, validate_input
from app.reasoning.ports import ObservationReasoningAgent


class _ReasoningRetrievalSession:
    """Add Observation Reasoning's refinement policy to the generic retrieval budget."""

    def __init__(self, executor: BoundedRetrievalExecutor) -> None:
        self._executor = executor

    @property
    def ledger(self):
        """Return the underlying metadata-only retrieval ledger."""
        return self._executor.ledger

    @property
    def consumed_slots(self) -> int:
        """Return the irreversible retrieval budget consumed by this session."""
        return self._executor.consumed_slots

    async def execute(self, request: KnowledgeRetrievalRequest) -> RetrievalOutcome:
        """Reject a refinement unless execution one returned at least one item."""
        if request.refinement is not None and not self._first_retrieval_has_items():
            return RetrievalRejected(rejection_reason="invalid_refinement")
        return await self._executor.execute(request)

    def _first_retrieval_has_items(self) -> bool:
        """Determine eligibility from the metadata projection of execution one."""
        first = next((attempt for attempt in self.ledger if attempt.execution_ordinal == 1), None)
        return first is not None and first.outcome == "retrieved" and bool(first.knowledge_refs)


class ObservationReasoningExecutor:
    """Coordinate validated evidence through isolated reasoning phases."""

    def __init__(self, agent: ObservationReasoningAgent, retriever: KnowledgeRetriever) -> None:
        """Bind framework-neutral agent and injected knowledge retriever."""
        self._agent = agent
        self._retriever = retriever

    async def execute(self, value) -> ReasoningOutcome:
        """Execute one side-effect-free reasoning run and fail closed safely."""
        try:
            value = validate_input(value)
            catalog = build_catalog(value)
            limitations = derive_limitations(value)
        except asyncio.CancelledError:
            raise
        except Exception:
            return ReasoningFailure(code="reasoning_result_invalid", component="result_builder")
        try:
            findings_completion = await self._agent.form_findings(
                __import__("app.reasoning.contracts", fromlist=["FindingRequest"]).FindingRequest(
                    context=value.context,
                    usable_results=value.usable_results,
                    relationships=value.relationships,
                    catalog=catalog,
                    limitations=limitations,
                )
            )
            findings = freeze_findings(findings_completion, catalog)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return ReasoningFailure(code="reasoning_model_timed_out", component="finding_phase")
        except UsageLimitExceeded:
            return ReasoningFailure(code="reasoning_policy_violated", component="finding_phase")
        except ReasoningPolicyViolation:
            return ReasoningFailure(code="reasoning_policy_violated", component="finding_phase")
        except UnexpectedModelBehavior:
            return ReasoningFailure(code="reasoning_result_invalid", component="finding_phase")
        except ValueError:
            return ReasoningFailure(code="reasoning_result_invalid", component="finding_phase")
        except Exception:
            return ReasoningFailure(code="reasoning_model_failed", component="finding_phase")
        hypotheses = ()
        if findings:
            retrieval = _ReasoningRetrievalSession(
                BoundedRetrievalExecutor(frozenset(item.id for item in findings), self._retriever)
            )
            try:
                from app.reasoning.contracts import HypothesisRequest

                completion = await self._agent.form_hypotheses(
                    HypothesisRequest(
                        context=value.context,
                        usable_results=value.usable_results,
                        relationships=value.relationships,
                        catalog=catalog,
                        findings=findings,
                        limitations=limitations,
                    ),
                    retrieval,
                )
                refs = tuple(
                    reference
                    for attempt in retrieval.ledger
                    for reference in attempt.knowledge_refs
                )
                hypotheses = validate_hypotheses(completion, findings, refs)
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                return ReasoningFailure(
                    code="reasoning_model_timed_out", component="hypothesis_phase"
                )
            except UsageLimitExceeded:
                return ReasoningFailure(
                    code="reasoning_policy_violated", component="hypothesis_phase"
                )
            except UnexpectedModelBehavior:
                return ReasoningFailure(
                    code="reasoning_result_invalid", component="hypothesis_phase"
                )
            except ReasoningPolicyViolation:
                return ReasoningFailure(
                    code="reasoning_policy_violated", component="hypothesis_phase"
                )
            except ValueError:
                return ReasoningFailure(
                    code="reasoning_result_invalid", component="hypothesis_phase"
                )
            except Exception:
                return ReasoningFailure(code="reasoning_model_failed", component="hypothesis_phase")
        try:
            from app.reasoning.contracts import OverallStateRequest

            overall = await self._agent.determine_overall_state(
                OverallStateRequest(
                    context=value.context,
                    usable_results=value.usable_results,
                    relationships=value.relationships,
                    catalog=catalog,
                    findings=findings,
                    limitations=limitations,
                )
            )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return ReasoningFailure(
                code="reasoning_model_timed_out", component="overall_state_phase"
            )
        except UsageLimitExceeded:
            return ReasoningFailure(
                code="reasoning_policy_violated", component="overall_state_phase"
            )
        except ReasoningPolicyViolation:
            return ReasoningFailure(
                code="reasoning_policy_violated", component="overall_state_phase"
            )
        except UnexpectedModelBehavior:
            return ReasoningFailure(
                code="reasoning_result_invalid", component="overall_state_phase"
            )
        except ValueError:
            return ReasoningFailure(
                code="reasoning_result_invalid", component="overall_state_phase"
            )
        except Exception:
            return ReasoningFailure(code="reasoning_model_failed", component="overall_state_phase")
        try:
            return ReasoningSuccess(
                result=build_result(value, findings, hypotheses, overall, limitations)
            )
        except Exception:
            return ReasoningFailure(code="reasoning_result_invalid", component="result_builder")
