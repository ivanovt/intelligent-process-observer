from __future__ import annotations

import math
from datetime import UTC, datetime

import httpx

from app.core.settings import BasicAuthCredentials, BearerTokenCredentials
from app.infrastructure.prometheus.contracts import (
    PrometheusRangeQueryResult,
    PrometheusRangeSample,
    PrometheusRangeSeries,
    PrometheusSourceProfile,
)


class PrometheusQueryError(Exception):
    """The provider rejected a query or returned an unusable query response."""


class PrometheusAuthenticationError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Prometheus authentication failed with status {status_code}")


class PrometheusTransportError(Exception):
    """The provider could not be reached or returned an unexpected system failure."""


class HttpxPrometheusQueryAdapter:
    timeout_seconds = 15.0
    maximum_samples = 60

    async def query_range(
        self,
        source: PrometheusSourceProfile,
        *,
        query: str,
        start: datetime,
        end: datetime,
    ) -> PrometheusRangeQueryResult:
        start = start.astimezone(UTC)
        end = end.astimezone(UTC)
        step_seconds = self._choose_step_seconds(start, end)
        headers, auth = self._authentication(source)
        url = f"{source.base_url.rstrip('/')}/api/v1/query_range"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    url,
                    data={
                        "query": query,
                        "start": start.timestamp(),
                        "end": end.timestamp(),
                        "step": step_seconds,
                    },
                    headers=headers,
                    auth=auth,
                )
        except httpx.RequestError as error:
            raise PrometheusTransportError("Could not reach Prometheus") from error

        if response.status_code in {401, 403}:
            raise PrometheusAuthenticationError(response.status_code)
        if response.status_code >= 500:
            raise PrometheusTransportError("Prometheus returned a system error")
        if response.status_code >= 400:
            raise PrometheusQueryError(self._error_message(response))

        try:
            payload = response.json()
            data = payload["data"]
            if payload.get("status") != "success" or data.get("resultType") != "matrix":
                raise PrometheusQueryError(self._error_message(response))
            series = [self._parse_series(item) for item in data["result"]]
            warnings = [str(warning) for warning in payload.get("warnings", [])]
        except (KeyError, TypeError, ValueError) as error:
            raise PrometheusQueryError("Prometheus returned an invalid query response") from error

        return PrometheusRangeQueryResult(
            resolved_start=start,
            resolved_end=end,
            step_seconds=step_seconds,
            series=series,
            warnings=warnings,
        )

    def _choose_step_seconds(self, start: datetime, end: datetime) -> int:
        duration_seconds = max(1, math.ceil((end - start).total_seconds()))
        return max(1, math.ceil(duration_seconds / self.maximum_samples))

    def _authentication(
        self, source: PrometheusSourceProfile
    ) -> tuple[dict[str, str], httpx.Auth | None]:
        credentials = source.credentials
        if isinstance(credentials, BearerTokenCredentials):
            return {"Authorization": f"Bearer {credentials.token.get_secret_value()}"}, None
        if isinstance(credentials, BasicAuthCredentials):
            return {}, httpx.BasicAuth(
                credentials.username, credentials.password.get_secret_value()
            )
        raise PrometheusTransportError("Unsupported Prometheus credential configuration")

    @staticmethod
    def _parse_series(payload: object) -> PrometheusRangeSeries:
        if not isinstance(payload, dict):
            raise ValueError("series must be an object")
        labels = payload.get("metric")
        values = payload.get("values")
        if not isinstance(labels, dict) or not isinstance(values, list):
            raise ValueError("series has an invalid shape")
        samples: list[PrometheusRangeSample] = []
        for sample in values:
            if not isinstance(sample, list) or len(sample) != 2:
                raise ValueError("sample has an invalid shape")
            timestamp, value = sample
            samples.append(
                PrometheusRangeSample(
                    timestamp=datetime.fromtimestamp(float(timestamp), tz=UTC),
                    value=str(value),
                )
            )
        return PrometheusRangeSeries(
            labels={str(key): str(value) for key, value in labels.items()}, samples=samples
        )

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
            message = payload.get("error")
            if isinstance(message, str) and message:
                return message
        except ValueError:
            pass
        return "Prometheus rejected the query"
