"""Shared timeout, normal-failure, budget, and trace behavior for analytical tools."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any

from agent_framework_experiment.domain.budget import ToolBudget, ToolBudgetExhausted
from agent_framework_experiment.domain.contracts import (
    AlertAnalysisInput,
    ToolAttemptTrace,
    ToolExecutionResult,
)
from agent_framework_experiment.domain.evidence_catalog import (
    attach_successful_tool_evidence,
    base_evidence_ids,
    successful_tool_evidence_ids,
)
from agent_framework_experiment.tools.analyses import (
    duration_outlier,
    recurrence_concentration,
    reference_pattern_analysis,
)

AnalyticalTool = Callable[
    [AlertAnalysisInput], ToolExecutionResult | Awaitable[ToolExecutionResult]
]

TOOL_NAMES = (
    "recurrence_concentration",
    "duration_outlier",
    "reference_pattern_analysis",
)


class AnalyticalToolExecutor:
    """The only component allowed to invoke optional analytical functions."""

    def __init__(
        self,
        input_data: AlertAnalysisInput,
        *,
        timeout_seconds: float = 1.0,
        handlers: dict[str, AnalyticalTool] | None = None,
        budget: ToolBudget | None = None,
    ) -> None:
        self.input_data = input_data
        self.timeout_seconds = timeout_seconds
        self.budget = budget or ToolBudget(limit=10)
        self.handlers: dict[str, AnalyticalTool] = {
            "recurrence_concentration": recurrence_concentration,
            "duration_outlier": duration_outlier,
            "reference_pattern_analysis": reference_pattern_analysis,
        }
        if handlers:
            unknown = set(handlers) - set(TOOL_NAMES)
            if unknown:
                raise ValueError(f"unknown analytical tools: {sorted(unknown)}")
            self.handlers.update(handlers)
        self._traces: list[ToolAttemptTrace] = []
        self._available_evidence_ids = set(base_evidence_ids(input_data))
        self.blocked_tool_calls = 0

    @property
    def traces(self) -> tuple[ToolAttemptTrace, ...]:
        return tuple(self._traces)

    @property
    def available_evidence_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._available_evidence_ids))

    async def invoke(self, tool_name: str) -> ToolExecutionResult:
        if tool_name not in self.handlers:
            raise ValueError(f"unknown analytical tool: {tool_name}")
        invocation_order = self.budget.reserve_attempt()
        started = perf_counter()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                candidate: Any = self.handlers[tool_name](self.input_data)
                result = await candidate if inspect.isawaitable(candidate) else candidate
                if not isinstance(result, ToolExecutionResult):
                    raise TypeError("analytical tools must return ToolExecutionResult")
        except TimeoutError:
            result = ToolExecutionResult(status="timeout", data={"reason": "tool_timeout"})
        except Exception:
            # Expected tool failures are data, never framework control-flow exceptions.
            result = ToolExecutionResult(status="failed", data={"reason": "tool_failed"})
        self._available_evidence_ids.update(successful_tool_evidence_ids(tool_name, result))
        result = attach_successful_tool_evidence(tool_name, result)
        latency_ms = (perf_counter() - started) * 1_000
        self._traces.append(
            ToolAttemptTrace(
                invocation_order=invocation_order,
                tool_name=tool_name,
                status=result.status,
                latency_ms=latency_ms,
            )
        )
        return result

    async def invoke_from_adapter(self, tool_name: str) -> ToolExecutionResult | dict[str, str]:
        """Keep an over-budget request from becoming a framework exception."""

        try:
            return await self.invoke(tool_name)
        except ToolBudgetExhausted:
            self.blocked_tool_calls += 1
            return {"status": "blocked", "reason": "analytical_tool_budget_exhausted"}
