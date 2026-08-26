from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.tools import tool

from agent_framework_experiment.observation_reasoning.common import (
    observation_evidence_ids,
    render_phase_one,
    render_phase_two,
    upstream_knowledge_refs,
)
from agent_framework_experiment.observation_reasoning.domain import (
    FindingFormationOutput,
    HypothesisFormationOutput,
    ObservationReasoningInput,
    ReasoningSettings,
)
from agent_framework_experiment.observation_reasoning.instructions import BASE_INSTRUCTIONS
from agent_framework_experiment.observation_reasoning.phase import build_result, freeze_findings
from agent_framework_experiment.observation_reasoning.retrieval import RetrievalExecutor
from agent_framework_experiment.shared.openrouter import build_langchain_openrouter_model


class LangChainReasoningAgent:
    def __init__(self, settings: ReasoningSettings | None = None) -> None:
        self.settings = settings or ReasoningSettings()

    async def analyze(self, input_data: ObservationReasoningInput, executor: RetrievalExecutor):
        model = build_langchain_openrouter_model(self.settings)
        phase_one = create_agent(
            model,
            tools=(),
            system_prompt=BASE_INSTRUCTIONS,
            response_format=ToolStrategy(FindingFormationOutput),
            name="reasoning_phase_one",
        )
        draft = (
            await phase_one.ainvoke(
                {"messages": [{"role": "user", "content": render_phase_one(input_data)}]}
            )
        )["structured_response"]
        frozen = freeze_findings(draft, allowed_evidence_refs=observation_evidence_ids(input_data))
        executor.set_frozen_findings(frozen)
        if not frozen.findings:
            return build_result(
                input_data, frozen, HypothesisFormationOutput(), available_knowledge_refs=()
            )

        @tool
        async def retrieve_knowledge(
            query: str,
            supported_finding_ids: tuple[str, ...],
            refines_attempt: int | None = None,
            unresolved_gap: str | None = None,
        ):
            """Retrieve deterministic knowledge grounded in frozen finding IDs only."""
            from agent_framework_experiment.observation_reasoning.retrieval import (
                KnowledgeRetrievalRequest,
            )

            return await executor.invoke(
                KnowledgeRetrievalRequest(
                    query=query,
                    supported_finding_ids=supported_finding_ids,
                    refines_attempt=refines_attempt,
                    unresolved_gap=unresolved_gap,
                )
            )

        phase_two = create_agent(
            model,
            tools=(retrieve_knowledge,),
            system_prompt=BASE_INSTRUCTIONS,
            response_format=ToolStrategy(HypothesisFormationOutput),
            name="reasoning_phase_two",
        )
        hypotheses = (
            await phase_two.ainvoke(
                {"messages": [{"role": "user", "content": render_phase_two(input_data, frozen)}]}
            )
        )["structured_response"]
        refs = (*upstream_knowledge_refs(input_data), *executor.available_hypothesis_refs)
        return build_result(input_data, frozen, hypotheses, available_knowledge_refs=refs)
