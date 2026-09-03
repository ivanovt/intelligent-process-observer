"""Source-aware, transport-free Prometheus Metric provider composition."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.core.settings import PrometheusCredentials, PrometheusSourceSettings
from app.infrastructure.prometheus.configuration import (
    _validate_prometheus_target,
    _ValidatedPrometheusTarget,
)
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricProviderScope,
    MetricSeriesAcquisitionFailure,
    MetricSeriesAcquisitionOutcome,
    MetricSeriesUnavailable,
)

_SOURCE_UNAVAILABLE = "prometheus_source_unavailable"
_INVALID_TARGET = "prometheus_source_invalid"
_TRANSPORT_NOT_IMPLEMENTED = "prometheus_transport_not_implemented"


@dataclass(frozen=True)
class _ConfiguredPrometheusSource:
    """An immutable snapshot of one shared source for later transport composition."""

    id: str
    base_url: str
    credentials: PrometheusCredentials


class PrometheusMetricSeriesProvider:
    """Resolve configured Prometheus sources behind the Metric provider port."""

    def __init__(self, sources: Iterable[PrometheusSourceSettings]) -> None:
        self._sources = {
            source.id: _ConfiguredPrometheusSource(
                id=source.id,
                base_url=source.base_url,
                credentials=source.credentials,
            )
            for source in sources
        }

    async def acquire(
        self, scope: MetricProviderScope, window: MetricAnalysisWindow
    ) -> MetricSeriesAcquisitionOutcome:
        """Resolve and validate only the requested source without starting transport work."""

        del window
        source = self._sources.get(scope.source_id)
        if source is None:
            return MetricSeriesUnavailable(diagnostic=_SOURCE_UNAVAILABLE)
        target = _validate_prometheus_target(source.base_url)
        if target is None:
            return MetricSeriesAcquisitionFailure(diagnostic=_INVALID_TARGET)
        return self._transport_unavailable(source, target)

    @staticmethod
    def _transport_unavailable(
        source: _ConfiguredPrometheusSource, target: _ValidatedPrometheusTarget
    ) -> MetricSeriesAcquisitionFailure:
        """Keep a validated selection private until VS-02 adds the HTTP boundary."""

        del source, target
        return MetricSeriesAcquisitionFailure(diagnostic=_TRANSPORT_NOT_IMPLEMENTED)
