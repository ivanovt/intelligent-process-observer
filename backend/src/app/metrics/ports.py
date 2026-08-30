"""Framework-neutral ports for the exercised Metric pipeline paths."""

from __future__ import annotations

from typing import Protocol

from app.metrics.contracts import (
    MetricAgentOutcome,
    MetricAgentRequest,
    MetricAnalysisWindow,
    MetricHistoryRead,
    MetricLensExecutionContext,
    MetricProviderScope,
    MetricSeriesAcquisitionOutcome,
    MetricToolOutcome,
)


class MetricSeriesProvider(Protocol):
    async def acquire(
        self, scope: MetricProviderScope, window: MetricAnalysisWindow
    ) -> MetricSeriesAcquisitionOutcome: ...


class MetricsAnalysisAgent(Protocol):
    async def complete(
        self, request: MetricAgentRequest, tools: MetricToolExecutor | None = None
    ) -> MetricAgentOutcome: ...


class MetricToolExecutor(Protocol):
    async def execute(self, name: str) -> MetricToolOutcome: ...


class MetricHistoryReader(Protocol):
    async def load(
        self, session: object, context: MetricLensExecutionContext
    ) -> MetricHistoryRead: ...
