from __future__ import annotations

import math
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import PrometheusSourceSettings, get_settings
from app.infrastructure.persistence.models import (
    MetricLensModel,
    ObservationModel,
    ObservationRelationshipModel,
)
from app.infrastructure.persistence.repository import ObservationRepository
from app.infrastructure.prometheus.adapter import (
    PrometheusAuthenticationError,
    PrometheusQueryError,
    PrometheusTransportError,
)
from app.infrastructure.prometheus.contracts import (
    PrometheusQueryAdapter,
    PrometheusRangeQueryResult,
    PrometheusSourceProfile,
)
from app.observations.contracts import (
    CapabilityAdapter,
    CapabilitySource,
    DefinitionCapabilities,
    LensReference,
    MetricLensResponse,
    MetricPreflightFailure,
    MetricPreflightRequest,
    MetricPreflightResponse,
    MetricPreflightSuccess,
    MetricSample,
    ObservationCreate,
    ObservationResponse,
    ObservationSummary,
    RelationshipReference,
    RelationshipResponse,
    SemanticDescriptor,
)
from app.observations.errors import ApiError

_OFFSET_UNITS = {"m": 60, "h": 60 * 60, "d": 24 * 60 * 60, "w": 7 * 24 * 60 * 60}
_OFFSET_RE = re.compile(r"^(?P<amount>[1-9][0-9]*)(?P<unit>[mhdw])$")
_MAXIMUM_LABEL_SET_DIAGNOSTICS = 10


class ObservationDefinitionService:
    def __init__(self, repository: ObservationRepository | None = None) -> None:
        self._repository = repository or ObservationRepository()

    def capabilities(self) -> DefinitionCapabilities:
        sources = [
            CapabilitySource(id=source.id, name=source.name)
            for source in self._configured_sources().values()
        ]
        if not sources:
            return DefinitionCapabilities(metric=[])
        return DefinitionCapabilities(
            metric=[CapabilityAdapter(adapter_type="prometheus", sources=sources)]
        )

    async def create(
        self, session: AsyncSession, definition: ObservationCreate
    ) -> ObservationResponse:
        for lens in definition.lenses:
            self._source_for(lens.source_id)
        async with session.begin():
            model = await self._repository.create(session, definition)
        return self.observation_response(model)

    async def list(self, session: AsyncSession) -> list[ObservationSummary]:
        return [self.observation_summary(model) for model in await self._repository.list(session)]

    async def get(self, session: AsyncSession, observation_id: UUID) -> ObservationResponse:
        model = await self._repository.get(session, observation_id)
        if model is None:
            raise ApiError(
                404,
                "observation_not_found",
                "Observation definition was not found",
            )
        return self.observation_response(model)

    async def get_lens(
        self, session: AsyncSession, observation_id: UUID, lens_id: str
    ) -> MetricLensResponse:
        model = await self._get_model(session, observation_id)
        for lens in model.lenses:
            if lens.lens_id == lens_id:
                return self.lens_response(model, lens)
        raise ApiError(404, "lens_not_found", "Lens definition was not found")

    async def get_relationship(
        self, session: AsyncSession, observation_id: UUID, relationship_id: str
    ) -> RelationshipResponse:
        model = await self._get_model(session, observation_id)
        for relationship in model.relationships:
            if relationship.relationship_id == relationship_id:
                return self.relationship_response(model, relationship)
        raise ApiError(404, "relationship_not_found", "Relationship definition was not found")

    async def preflight_metric(
        self,
        request: MetricPreflightRequest,
        adapter: PrometheusQueryAdapter,
        *,
        now: datetime | None = None,
    ) -> MetricPreflightResponse:
        source = self._source_for(request.source_id)
        end = (now or datetime.now(UTC)).astimezone(UTC)
        start = end - self._duration(request.validation_window.duration)
        try:
            result = await adapter.query_range(source, query=request.query, start=start, end=end)
        except PrometheusQueryError as error:
            return MetricPreflightFailure(valid=False, code="query_rejected", message=str(error))
        except PrometheusAuthenticationError as error:
            raise ApiError(
                error.status_code,
                "provider_authentication_failed",
                "Prometheus authentication or authorization failed",
            ) from error
        except PrometheusTransportError as error:
            raise ApiError(502, "provider_unavailable", "Prometheus is unavailable") from error
        except Exception as error:
            raise ApiError(502, "provider_failure", "Prometheus preflight failed") from error

        try:
            return self._preflight_response(result)
        except (TypeError, ValueError) as error:
            raise ApiError(
                502,
                "provider_failure",
                "Prometheus returned invalid sample data",
            ) from error

    def observation_summary(self, model: ObservationModel) -> ObservationSummary:
        href = self._observation_href(model.id)
        return ObservationSummary(
            id=model.id,
            name=model.name,
            description=model.description,
            objective=model.objective,
            schema_version=model.schema_version,
            lenses=[self.lens_reference(model, lens) for lens in model.lenses],
            relationships=[
                self.relationship_reference(model, relationship)
                for relationship in model.relationships
            ],
            href=href,
        )

    def observation_response(self, model: ObservationModel) -> ObservationResponse:
        summary = self.observation_summary(model)
        return ObservationResponse(
            **summary.model_dump(),
            lenses=[self.lens_response(model, lens) for lens in model.lenses],
            relationships=[
                self.relationship_response(model, relationship)
                for relationship in model.relationships
            ],
        )

    def lens_reference(self, model: ObservationModel, lens: MetricLensModel) -> LensReference:
        return LensReference(
            id=lens.lens_id,
            name=lens.name,
            type="metric",
            href=f"{self._observation_href(model.id)}/lenses/{lens.lens_id}",
        )

    def lens_response(self, model: ObservationModel, lens: MetricLensModel) -> MetricLensResponse:
        return MetricLensResponse(
            id=lens.lens_id,
            name=lens.name,
            description=lens.description,
            type="metric",
            metric_id=lens.metric_id,
            adapter_type="prometheus",
            source_id=lens.source_id,
            query=lens.query,
            unit=lens.unit,
            analysis_objectives=lens.analysis_objectives,
            reference_periods=lens.reference_periods,
            href=f"{self._observation_href(model.id)}/lenses/{lens.lens_id}",
            observation_href=self._observation_href(model.id),
        )

    def relationship_reference(
        self, model: ObservationModel, relationship: ObservationRelationshipModel
    ) -> RelationshipReference:
        return RelationshipReference(
            id=relationship.relationship_id,
            name=relationship.name,
            href=f"{self._observation_href(model.id)}/relationships/{relationship.relationship_id}",
        )

    def relationship_response(
        self, model: ObservationModel, relationship: ObservationRelationshipModel
    ) -> RelationshipResponse:
        return RelationshipResponse(
            id=relationship.relationship_id,
            name=relationship.name,
            description=relationship.description,
            participants=relationship.participants,
            conditions={
                key: SemanticDescriptor.model_validate(value)
                for key, value in relationship.conditions.items()
            },
            expected={
                key: SemanticDescriptor.model_validate(value)
                for key, value in relationship.expected.items()
            },
            href=f"{self._observation_href(model.id)}/relationships/{relationship.relationship_id}",
            observation_href=self._observation_href(model.id),
        )

    async def _get_model(self, session: AsyncSession, observation_id: UUID) -> ObservationModel:
        model = await self._repository.get(session, observation_id)
        if model is None:
            raise ApiError(404, "observation_not_found", "Observation definition was not found")
        return model

    def _source_for(self, source_id: str) -> PrometheusSourceProfile:
        source = self._configured_sources().get(source_id)
        if source is None:
            raise ApiError(
                422,
                "source_not_enabled",
                "The Prometheus source is not enabled",
                field="source_id",
            )
        return self._source_profile(source)

    @staticmethod
    def _source_profile(source: PrometheusSourceSettings) -> PrometheusSourceProfile:
        return PrometheusSourceProfile(
            id=source.id,
            name=source.name,
            base_url=source.base_url,
            credentials=source.credentials,
        )

    @staticmethod
    def _configured_sources() -> dict[str, PrometheusSourceSettings]:
        return {source.id: source for source in get_settings().prometheus_sources}

    @staticmethod
    def _observation_href(observation_id: UUID) -> str:
        return f"/api/v1/observations/{observation_id}"

    @staticmethod
    def _duration(duration: str) -> timedelta:
        match = _OFFSET_RE.fullmatch(duration)
        if match is None:
            raise ValueError("duration must be validated before it reaches the service")
        return timedelta(seconds=int(match.group("amount")) * _OFFSET_UNITS[match.group("unit")])

    @staticmethod
    def _preflight_response(result: PrometheusRangeQueryResult) -> MetricPreflightResponse:
        series_count = len(result.series)
        if series_count != 1:
            return MetricPreflightFailure(
                valid=False,
                code=("no_series_returned" if series_count == 0 else "multiple_series_returned"),
                message="The query must resolve to exactly one time series",
                series_count=series_count,
                label_sets=[
                    series.labels for series in result.series[:_MAXIMUM_LABEL_SET_DIAGNOSTICS]
                ],
                warnings=result.warnings,
            )
        series = result.series[0]
        return MetricPreflightSuccess(
            valid=True,
            resolved_start=result.resolved_start.isoformat(),
            resolved_end=result.resolved_end.isoformat(),
            step_seconds=result.step_seconds,
            labels=series.labels,
            samples=[
                ObservationDefinitionService._metric_sample(sample.timestamp, sample.value)
                for sample in series.samples
            ],
            warnings=result.warnings,
        )

    @staticmethod
    def _metric_sample(timestamp: datetime, raw_value: str) -> MetricSample:
        value = float(raw_value)
        if math.isfinite(value):
            return MetricSample(
                timestamp=timestamp.astimezone(UTC).isoformat(),
                value=value,
                value_status="finite",
            )
        if math.isnan(value):
            return MetricSample(
                timestamp=timestamp.astimezone(UTC).isoformat(),
                value=None,
                value_status="nan",
            )
        return MetricSample(
            timestamp=timestamp.astimezone(UTC).isoformat(),
            value=None,
            value_status="positive_infinity" if value > 0 else "negative_infinity",
        )
