from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.core.settings import PrometheusCredentials


@dataclass(frozen=True)
class PrometheusSourceProfile:
    id: str
    name: str
    base_url: str
    credentials: PrometheusCredentials


@dataclass(frozen=True)
class PrometheusRangeSample:
    timestamp: datetime
    value: str


@dataclass(frozen=True)
class PrometheusRangeSeries:
    labels: dict[str, str]
    samples: list[PrometheusRangeSample]


@dataclass(frozen=True)
class PrometheusRangeQueryResult:
    resolved_start: datetime
    resolved_end: datetime
    step_seconds: int
    series: list[PrometheusRangeSeries]
    warnings: list[str]


class PrometheusQueryAdapter(Protocol):
    async def query_range(
        self,
        source: PrometheusSourceProfile,
        *,
        query: str,
        start: datetime,
        end: datetime,
    ) -> PrometheusRangeQueryResult: ...
