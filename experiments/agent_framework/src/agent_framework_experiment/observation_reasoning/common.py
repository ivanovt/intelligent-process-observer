"""Canonical phase inputs and scripted execution shared by framework adapters."""

from __future__ import annotations

import json

from agent_framework_experiment.observation_reasoning.domain import ObservationReasoningInput


def observation_evidence_ids(input_data: ObservationReasoningInput) -> tuple[str, ...]:
    return tuple(
        sorted(
            item.evidence_id
            for item in (*input_data.usable_evidence, *input_data.relationship_evidence)
        )
    )


def upstream_knowledge_refs(input_data: ObservationReasoningInput):
    return tuple(ref for item in input_data.upstream_log_knowledge for ref in item.knowledge_refs)


def render_phase_one(input_data: ObservationReasoningInput) -> str:
    return json.dumps(
        {
            "observation_reasoning_input": input_data.model_dump(mode="json"),
            "available_observation_evidence_ids": observation_evidence_ids(input_data),
            "instruction": (
                "Form findings only from available_observation_evidence_ids. "
                "Upstream knowledge is not finding evidence."
            ),
        },
        indent=2,
        sort_keys=True,
    )


def render_phase_two(input_data: ObservationReasoningInput, frozen) -> str:
    return json.dumps(
        {
            "frozen_findings": [item.model_dump(mode="json") for item in frozen.findings],
            "upstream_knowledge_refs": [
                item.model_dump(mode="json") for item in upstream_knowledge_refs(input_data)
            ],
            "instruction": (
                "Findings are frozen. Form only knowledge-grounded hypotheses; "
                "use retrieve_knowledge only for frozen finding IDs."
            ),
        },
        indent=2,
        sort_keys=True,
    )
