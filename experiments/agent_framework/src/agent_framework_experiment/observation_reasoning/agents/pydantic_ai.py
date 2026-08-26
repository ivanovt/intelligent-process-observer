from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModelSettings

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
from agent_framework_experiment.shared.openrouter import (
    build_pydantic_openrouter_model,
    provider_preferences,
)


class PydanticAIReasoningAgent:
    def __init__(self, settings: ReasoningSettings | None = None) -> None:
        self.settings = settings or ReasoningSettings()

    def _settings(self) -> OpenAIChatModelSettings:
        return OpenAIChatModelSettings(
            max_tokens=self.settings.max_output_tokens,
            parallel_tool_calls=False,
            openai_reasoning_effort=self.settings.reasoning_effort,
            extra_body={"provider": provider_preferences(self.settings)},
        )

    async def analyze(self, input_data: ObservationReasoningInput, executor: RetrievalExecutor):
        model = build_pydantic_openrouter_model(self.settings)
        phase_one = Agent(
            model,
            output_type=FindingFormationOutput,
            instructions=BASE_INSTRUCTIONS,
            model_settings=self._settings(),
            retries=0,
        )
        draft = (await phase_one.run(render_phase_one(input_data))).output
        frozen = freeze_findings(draft, allowed_evidence_refs=observation_evidence_ids(input_data))
        executor.set_frozen_findings(frozen)
        if not frozen.findings:
            return build_result(
                input_data, frozen, HypothesisFormationOutput(), available_knowledge_refs=()
            )

        async def retrieve_knowledge(
            query: str,
            supported_finding_ids: tuple[str, ...],
            refines_attempt: int | None = None,
            unresolved_gap: str | None = None,
        ):
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

        phase_two = Agent(
            model,
            output_type=HypothesisFormationOutput,
            instructions=BASE_INSTRUCTIONS,
            model_settings=self._settings(),
            retries=0,
            tools=(retrieve_knowledge,),
        )
        hypotheses = (await phase_two.run(render_phase_two(input_data, frozen))).output
        refs = (*upstream_knowledge_refs(input_data), *executor.available_hypothesis_refs)
        return build_result(input_data, frozen, hypotheses, available_knowledge_refs=refs)
