"""Framework-neutral ports for the Metric pipeline's exercised VS-01 path."""

from __future__ import annotations

from typing import Protocol

from app.metrics.contracts import (
    MetricAgentOutcome,
    MetricAgentRequest,
    MetricAnalysisWindow,
    MetricHistoryEmpty,
    MetricLensExecutionContext,
    MetricProviderScope,
    MetricSeriesAcquisitionOutcome,
)


class MetricSeriesProvider(Protocol):
    async def acquire(
        self, scope: MetricProviderScope, window: MetricAnalysisWindow
    ) -> MetricSeriesAcquisitionOutcome: ...


class MetricsAnalysisAgent(Protocol):
    async def complete(self, request: MetricAgentRequest) -> MetricAgentOutcome: ...


class MetricHistoryReader(Protocol):
    async def load_empty(
        self, session: object, context: MetricLensExecutionContext
    ) -> MetricHistoryEmpty: ...
