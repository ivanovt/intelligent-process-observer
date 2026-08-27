"""Framework-neutral ports for the Metric pipeline's exercised VS-01 path."""

from __future__ import annotations

from typing import Protocol

from app.metrics.contracts import (
    MetricAgentCompletion,
    MetricAgentUsableRequest,
    MetricAnalysisWindow,
    MetricHistoryEmpty,
    MetricLensExecutionContext,
    MetricProviderScope,
    MetricSeriesAvailable,
)


class MetricSeriesProvider(Protocol):
    async def acquire(
        self, scope: MetricProviderScope, window: MetricAnalysisWindow
    ) -> MetricSeriesAvailable: ...


class MetricsAnalysisAgent(Protocol):
    async def complete(self, request: MetricAgentUsableRequest) -> MetricAgentCompletion: ...


class MetricHistoryReader(Protocol):
    async def load_empty(
        self, session: object, context: MetricLensExecutionContext
    ) -> MetricHistoryEmpty: ...
