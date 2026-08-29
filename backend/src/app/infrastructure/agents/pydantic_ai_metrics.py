"""PydanticAI adapter for the framework-neutral Metrics Agent port.

The injected model is intentionally the only provider-facing dependency.  Domain
requests and the application-owned tool ledger remain outside this module.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from app.metrics.contracts import (
    MetricAgentCompletion,
    MetricAgentOperationalFailure,
    MetricAgentRequest,
    MetricAgentUsableRequest,
)
from app.metrics.ports import MetricToolExecutor


class PydanticAIMetricsAgent:
    """Translate fixed Metric requests to an injected PydanticAI model."""

    def __init__(self, model: Model) -> None:
        self._model = model

    async def complete(
        self,
        request: MetricAgentRequest,
        tools: MetricToolExecutor | None = None,
    ) -> MetricAgentCompletion | MetricAgentOperationalFailure:
        if not isinstance(request, MetricAgentUsableRequest):
            return await self._run_without_tools(request)
        if tools is None:
            return MetricAgentOperationalFailure()
        requested: set[str] = set()

        async def invoke(name: str) -> dict[str, object]:
            if name in requested:
                raise RuntimeError(f"duplicate Metrics tool request: {name}")
            requested.add(name)
            outcome = await tools.execute(name)  # type: ignore[arg-type]
            return outcome.model_dump(mode="json")

        agent = Agent(self._model, output_type=MetricAgentCompletion, retries=0)

        @agent.tool_plain(name="spike", retries=0)
        async def spike() -> dict[str, object]:
            return await invoke("spike")

        @agent.tool_plain(name="oscillation", retries=0)
        async def oscillation() -> dict[str, object]:
            return await invoke("oscillation")

        @agent.tool_plain(name="stuck_signal", retries=0)
        async def stuck_signal() -> dict[str, object]:
            return await invoke("stuck_signal")

        try:
            result = await agent.run(
                request.model_dump_json(), usage_limits=UsageLimits(request_limit=4)
            )
            return MetricAgentCompletion.model_validate(result.output)
        except Exception:
            return MetricAgentOperationalFailure()

    async def _run_without_tools(
        self, request: MetricAgentRequest
    ) -> MetricAgentCompletion | MetricAgentOperationalFailure:
        agent = Agent(self._model, output_type=MetricAgentCompletion, retries=0)
        try:
            result = await agent.run(
                request.model_dump_json(), usage_limits=UsageLimits(request_limit=4)
            )
            return MetricAgentCompletion.model_validate(result.output)
        except Exception:
            return MetricAgentOperationalFailure()
