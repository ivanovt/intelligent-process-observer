"""Deterministic boundary tests for the PydanticAI Observation reasoning adapter."""

from __future__ import annotations

import asyncio

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.infrastructure.agents.pydantic_ai_reasoning import PydanticAIObservationReasoningAgent
from app.knowledge.contracts import (
    KnowledgeReference,
    RetrievalRefinement,
    RetrievedKnowledgeItem,
)
from app.knowledge.executor import BoundedRetrievalExecutor
from app.reasoning.contracts import (
    EvidenceCatalogEntry,
    EvidenceReference,
    Finding,
    FindingRequest,
    HypothesisRequest,
    ObservationIdentity,
    ObservationSemanticContext,
    OverallStateRequest,
    ReasoningLens,
    ReasoningPolicyViolation,
)


def run(coroutine):
    """Run one adapter coroutine without sharing an event loop between tests."""
    return asyncio.run(coroutine)


def context() -> ObservationSemanticContext:
    """Return the smallest LLM-safe context needed by every invocation."""
    from uuid import uuid4

    return ObservationSemanticContext(
        identity=ObservationIdentity(observation_id=uuid4(), observation_run_id=uuid4()),
        name="Observation",
        lenses=(ReasoningLens(lens_id="metric", lens_type="metric", name="Metric"),),
    )


def catalog() -> tuple[EvidenceCatalogEntry, ...]:
    """Return one catalog entry that can be referenced by a finding."""
    return (
        EvidenceCatalogEntry(
            id="evidence_0001",
            reference=EvidenceReference(
                source_type="metric_result", source_id="result", locator=("evidence", "mean")
            ),
        ),
    )


def finding_request() -> FindingRequest:
    """Build an evidence-only finding request."""
    return FindingRequest(
        context=context(), usable_results=(), relationships=(), catalog=catalog(), limitations=()
    )


def finding() -> Finding:
    """Build the frozen finding admitted to hypothesis/state phases."""
    return Finding(
        id="f-1", statement="Temperature changed.", evidence_refs=(catalog()[0].reference,)
    )


def hypothesis_request() -> HypothesisRequest:
    """Build the hypothesis request with exactly one frozen finding."""
    return HypothesisRequest(
        context=context(),
        usable_results=(),
        relationships=(),
        catalog=catalog(),
        findings=(finding(),),
        limitations=(),
    )


def overall_request() -> OverallStateRequest:
    """Build the isolated overall-state request."""
    return OverallStateRequest(
        context=context(),
        usable_results=(),
        relationships=(),
        catalog=catalog(),
        findings=(finding(),),
        limitations=(),
    )


def scripted_model(responses):
    """Inject scripted PydanticAI responses and retain their observed inputs."""
    calls = []

    def scripted(messages, info: AgentInfo) -> ModelResponse:
        calls.append((messages, info))
        return responses[len(calls) - 1](info)

    return FunctionModel(scripted), calls


def output(payload):
    """Return a script that emits the invocation's typed output tool."""
    return lambda info: ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, payload)])


def tool(arguments):
    """Return a script that requests the sole legal retrieval tool."""
    return lambda _: ModelResponse(parts=[ToolCallPart("retrieve_knowledge", arguments)])


class Retriever:
    """Script a typed retrieval batch while recording admitted calls."""

    def __init__(self, batches=()) -> None:
        self.batches = list(batches)
        self.calls = []

    async def retrieve(self, request):
        """Record the request and return the next configured batch."""
        self.calls.append(request)
        value = self.batches.pop(0) if self.batches else ()
        if isinstance(value, BaseException):
            raise value
        return value


def retrieval(retriever: Retriever) -> BoundedRetrievalExecutor:
    """Bind a fresh two-call retrieval budget to the single frozen finding."""
    return BoundedRetrievalExecutor(frozenset({"f-1"}), retriever)


def prompt(messages) -> str:
    """Extract the JSON user projection sent to a function model."""
    return next(
        part.content
        for message in messages
        for part in message.parts
        if part.part_kind == "user-prompt"
    )


def system_prompt(messages) -> str:
    """Extract server-owned instructions from a function-model request."""
    return " ".join(
        " ".join(part.content.split())
        for message in messages
        for part in message.parts
        if part.part_kind == "system-prompt"
    )


def test_findings_are_structured_single_request_with_no_tools_and_exact_projection() -> None:
    request = finding_request()
    model, calls = scripted_model([output({"findings": ()})])
    value = run(PydanticAIObservationReasoningAgent(model).form_findings(request))
    assert value.findings == () and len(calls) == 1
    messages, info = calls[0]
    assert not info.function_tools
    assert info.model_settings == {"timeout": 120, "max_tokens": 12_288}
    assert prompt(messages) == request.model_dump_json()
    system_prompt = " ".join(
        part.content
        for message in messages
        for part in message.parts
        if part.part_kind == "system-prompt"
    ).lower()
    assert "external knowledge" in system_prompt
    assert "alert record" in system_prompt and "untrusted" in system_prompt


def test_hypothesis_retrieval_trajectories_and_refinement_are_bounded() -> None:
    reference = KnowledgeReference(source_id="manual", reference="section-1")
    retriever = Retriever(
        [(RetrievedKnowledgeItem(statement="fact", references=(reference,)),), ()]
    )
    model, calls = scripted_model(
        [
            tool({"query": "first", "finding_ids": ["f-1"]}),
            tool(
                {"query": "refine", "finding_ids": ["f-1"], "refinement": {"unresolved_gap": "gap"}}
            ),
            output({"hypotheses": ()}),
        ]
    )
    value = run(
        PydanticAIObservationReasoningAgent(model).form_hypotheses(
            hypothesis_request(), retrieval(retriever)
        )
    )
    assert value.hypotheses == () and len(calls) == 3
    assert [item.query for item in retriever.calls] == ["first", "refine"]
    assert retriever.calls[1].refinement == RetrievalRefinement(unresolved_gap="gap")
    assert [tool_def.name for tool_def in calls[0][1].function_tools] == ["retrieve_knowledge"]
    instructions = system_prompt(calls[0][0]).lower()
    for clause in (
        "retrieval is optional",
        "frozen finding ids",
        "independent or refine",
        "exact knowledge references",
        "preserved upstream",
        "`hypotheses=[]`",
        "never invent a reference",
        "untrusted knowledge-only data",
    ):
        assert clause in instructions
    for _, info in calls:
        assert info.model_settings == {
            "timeout": 120,
            "max_tokens": 12_288,
            "parallel_tool_calls": False,
        }


@pytest.mark.parametrize(
    "responses",
    [
        [tool({"query": "bad", "finding_ids": ["unknown"]})],
        [
            lambda _: ModelResponse(
                parts=[
                    ToolCallPart("retrieve_knowledge", {"query": "a", "finding_ids": ["f-1"]}),
                    ToolCallPart("retrieve_knowledge", {"query": "b", "finding_ids": ["f-1"]}),
                ]
            )
        ],
        [tool({"query": "first", "finding_ids": ["f-1"], "refinement": {"unresolved_gap": "gap"}})],
        [
            tool({"query": "one", "finding_ids": ["f-1"]}),
            tool({"query": "two", "finding_ids": ["f-1"]}),
            tool({"query": "three", "finding_ids": ["f-1"]}),
        ],
    ],
)
def test_hypothesis_policy_rejects_unknown_parallel_invalid_refinement_and_final_slot(
    responses,
) -> None:
    model, _ = scripted_model(responses)
    with pytest.raises(ReasoningPolicyViolation):
        run(
            PydanticAIObservationReasoningAgent(model).form_hypotheses(
                hypothesis_request(), retrieval(Retriever())
            )
        )


def test_empty_or_failed_first_retrieval_allows_only_an_independent_second_call() -> None:
    model, _ = scripted_model(
        [
            tool({"query": "first", "finding_ids": ["f-1"]}),
            tool(
                {"query": "refine", "finding_ids": ["f-1"], "refinement": {"unresolved_gap": "gap"}}
            ),
        ]
    )
    with pytest.raises(ReasoningPolicyViolation):
        run(
            PydanticAIObservationReasoningAgent(model).form_hypotheses(
                hypothesis_request(), retrieval(Retriever([()]))
            )
        )

    retriever = Retriever([TimeoutError(), ()])
    model, calls = scripted_model(
        [
            tool({"query": "first", "finding_ids": ["f-1"]}),
            tool({"query": "independent", "finding_ids": ["f-1"]}),
            output({"hypotheses": ()}),
        ]
    )
    assert (
        run(
            PydanticAIObservationReasoningAgent(model).form_hypotheses(
                hypothesis_request(), retrieval(retriever)
            )
        ).hypotheses
        == ()
    )
    assert len(calls) == 3 and len(retriever.calls) == 2


def test_overall_state_is_structured_single_request_without_tools_or_hypothesis_channel() -> None:
    request = overall_request()
    model, calls = scripted_model([output({"overall_state": "uncertain"})])
    value = run(PydanticAIObservationReasoningAgent(model).determine_overall_state(request))
    assert value.overall_state == "uncertain" and len(calls) == 1
    messages, info = calls[0]
    assert not info.function_tools
    assert info.model_settings == {"timeout": 120, "max_tokens": 12_288}
    sent = prompt(messages)
    assert sent == request.model_dump_json()
    assert "hypotheses" not in sent and "knowledge" not in sent


@pytest.mark.parametrize(
    ("phase", "invoke"),
    [
        ("finding", lambda agent: agent.form_findings(finding_request())),
        ("overall", lambda agent: agent.determine_overall_state(overall_request())),
    ],
)
def test_no_tool_reasoning_phases_reject_non_output_tool_calls_as_policy_violations(
    phase: str, invoke
) -> None:
    """Forbidden calls are distinguished from malformed typed completions."""
    del phase
    model, calls = scripted_model([tool({"query": "forbidden", "finding_ids": ["f-1"]})])
    with pytest.raises(ReasoningPolicyViolation):
        run(invoke(PydanticAIObservationReasoningAgent(model)))
    assert len(calls) == 1


@pytest.mark.parametrize("failure", [TimeoutError("deadline"), RuntimeError("provider failure")])
def test_model_failures_and_invalid_completion_propagate_once_without_retry(
    failure: Exception,
) -> None:
    model, calls = scripted_model([lambda _: (_ for _ in ()).throw(failure)])
    with pytest.raises(type(failure)):
        run(PydanticAIObservationReasoningAgent(model).form_findings(finding_request()))
    assert len(calls) == 1

    model, calls = scripted_model(
        [output({"findings": [{"id": "bad", "statement": "x", "evidence_ids": []}]})]
    )
    with pytest.raises(UnexpectedModelBehavior):
        run(PydanticAIObservationReasoningAgent(model).form_findings(finding_request()))
    assert len(calls) == 1


def test_request_limits_and_framework_isolation_are_enforced() -> None:
    model, calls = scripted_model([tool({"query": "one", "finding_ids": ["f-1"]})] * 4)
    with pytest.raises((ReasoningPolicyViolation, UsageLimitExceeded)):
        run(
            PydanticAIObservationReasoningAgent(model).form_hypotheses(
                hypothesis_request(), retrieval(Retriever())
            )
        )
    assert len(calls) <= 3

    source = __import__("inspect").getsource(__import__("app.reasoning.ports", fromlist=["*"]))
    assert "pydantic_ai" not in source
