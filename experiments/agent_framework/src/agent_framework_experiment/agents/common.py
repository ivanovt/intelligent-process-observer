"""Shared adapter input rendering and deterministic scripted harness."""

from __future__ import annotations

import json
from collections.abc import Iterable

from agent_framework_experiment.domain.contracts import (
    AgentRunResult,
    AlertAnalysisAgentOutput,
    AlertAnalysisInput,
)
from agent_framework_experiment.domain.evidence_catalog import base_evidence_ids
from agent_framework_experiment.tools.executor import AnalyticalToolExecutor


def render_input(input_data: AlertAnalysisInput) -> str:
    payload = {
        "alert_lens_input": input_data.model_dump(mode="json"),
        "available_evidence_ids": base_evidence_ids(input_data),
    }
    return (
        "Immutable Alert Lens input and experiment-local evidence catalog (JSON):\n"
        + json.dumps(payload, indent=2, sort_keys=True)
    )


async def run_scripted_trajectory(
    input_data: AlertAnalysisInput,
    output: AlertAnalysisAgentOutput,
    tool_sequence: Iterable[str],
    *,
    executor: AnalyticalToolExecutor | None = None,
) -> AgentRunResult:
    """Deterministic test-only trajectory used identically by both adapters."""

    active_executor = executor or AnalyticalToolExecutor(input_data)
    for tool_name in tool_sequence:
        await active_executor.invoke_from_adapter(tool_name)
    return AgentRunResult(
        output=output,
        tool_attempts=active_executor.traces,
        available_evidence_ids=active_executor.available_evidence_ids,
        blocked_tool_calls=active_executor.blocked_tool_calls,
    )
