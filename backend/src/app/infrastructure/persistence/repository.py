"""Async repository operations for the internal runtime persistence aggregate."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.models import (
    LensAnalysisResultModel,
    LensRunModel,
    MetricLensModel,
    ObservationAnalysisResultModel,
    ObservationModel,
    ObservationRelationshipModel,
    ObservationReportModel,
    ObservationRunModel,
    RelationshipEvaluationModel,
)
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensRunInput,
    LensRunStatus,
    LensType,
    ObservationAnalysisResultInput,
    ObservationReportInput,
    ObservationRunInput,
    ObservationRunStatus,
    RelationshipEvaluationInput,
    StructuredReason,
    validate_lens_run_transition,
    validate_observation_run_transition,
)
from app.metrics.contracts import (
    MetricHistoryCandidate,
    MetricHistoryCandidates,
    MetricHistoryEmpty,
    MetricHistoryRead,
    MetricLensExecutionContext,
)
from app.observations.contracts import ObservationCreate


class ObservationRepository:
    async def create(
        self, session: AsyncSession, definition: ObservationCreate
    ) -> ObservationModel:
        observation = ObservationModel(
            name=definition.name,
            description=definition.description,
            objective=definition.objective,
            lenses=[
                MetricLensModel(
                    lens_id=lens.id,
                    name=lens.name,
                    description=lens.description,
                    adapter_type=lens.adapter_type,
                    source_id=lens.source_id,
                    metric_id=lens.metric_id,
                    query=lens.query,
                    unit=lens.unit,
                    analysis_objectives=[objective.value for objective in lens.analysis_objectives],
                    reference_periods=lens.reference_periods,
                    position=index,
                )
                for index, lens in enumerate(definition.lenses)
            ],
            relationships=[
                ObservationRelationshipModel(
                    relationship_id=relationship.id,
                    name=relationship.name,
                    description=relationship.description,
                    participants=relationship.participants,
                    conditions={
                        key: value.model_dump(mode="json")
                        for key, value in relationship.conditions.items()
                    },
                    expected={
                        key: value.model_dump(mode="json")
                        for key, value in relationship.expected.items()
                    },
                    position=index,
                )
                for index, relationship in enumerate(definition.relationships)
            ],
        )
        session.add(observation)
        await session.flush()
        await session.refresh(observation, attribute_names=["lenses", "relationships"])
        return observation

    async def list(self, session: AsyncSession) -> list[ObservationModel]:
        result = await session.scalars(
            select(ObservationModel)
            .options(
                selectinload(ObservationModel.lenses),
                selectinload(ObservationModel.relationships),
            )
            .order_by(ObservationModel.creation_order)
        )
        return list(result.unique())

    async def get(self, session: AsyncSession, observation_id: UUID) -> ObservationModel | None:
        result = await session.scalars(
            select(ObservationModel)
            .where(ObservationModel.id == observation_id)
            .options(
                selectinload(ObservationModel.lenses),
                selectinload(ObservationModel.relationships),
            )
        )
        return result.unique().one_or_none()


class RuntimePersistenceRepository:
    """Persist and retrieve runtime state inside the caller-owned async transaction.

    Operations flush for immediate integrity feedback but never commit; orchestration or
    other callers decide the transaction boundary when composing multiple runtime writes.
    """

    async def load(
        self,
        session: AsyncSession,
        context: MetricLensExecutionContext,
    ) -> MetricHistoryRead:
        """Load the bounded, usable Metric History projection for one Lens identity.

        Metric result timestamps are normalized UTC strings by the strict result contract,
        so PostgreSQL JSON string ordering is the same as event-time ordering.  The query
        fetches only the newest effective lookback, then restores chronological order for
        the framework-neutral History analyzer.
        """

        payload = LensAnalysisResultModel.payload
        window_end = payload["analysis_window"]["to"].as_string()
        window_start = payload["analysis_window"]["from"].as_string()
        data_quality = payload["data_quality"].as_string()
        result = await session.execute(
            select(
                LensAnalysisResultModel.lens_run_id,
                LensAnalysisResultModel.status,
                payload,
            )
            .join(LensRunModel, LensAnalysisResultModel.lens_run_id == LensRunModel.id)
            .join(
                ObservationRunModel,
                LensRunModel.observation_run_id == ObservationRunModel.id,
            )
            .where(
                ObservationRunModel.observation_id == context.identity.observation_id,
                LensRunModel.lens_id == context.identity.lens_id,
                LensRunModel.id != context.identity.lens_run_id,
                LensAnalysisResultModel.result_type == LensType.METRIC.value,
                LensAnalysisResultModel.status.in_(
                    (LensRunStatus.COMPLETED.value, LensRunStatus.PARTIAL.value)
                ),
                data_quality.in_(("good", "degraded")),
                window_end < context.analysis_window.to.isoformat().replace("+00:00", "Z"),
            )
            .order_by(
                window_end.desc(),
                window_start.desc(),
                cast(LensRunModel.id, String).desc(),
            )
            .limit(context.history_policy.lookback_runs)
        )
        candidates = tuple(
            MetricHistoryCandidate.model_validate_json(
                json.dumps(
                    {
                        "lens_run_id": str(row.lens_run_id),
                        "analysis_window": row.payload["analysis_window"],
                        "status": row.status,
                        "data_quality": row.payload["data_quality"],
                        "mean": row.payload["evidence"]["current"]["mean"],
                    }
                )
            )
            for row in result
        )
        if not candidates:
            return MetricHistoryEmpty()
        return MetricHistoryCandidates(candidates=tuple(reversed(candidates)))

    async def create_observation_run(
        self, session: AsyncSession, request: ObservationRunInput
    ) -> ObservationRunModel:
        """Add a pending ObservationRun correlated with an existing definition."""

        observation_run = ObservationRunModel(
            id=request.id,
            observation_id=request.observation_id,
            status=request.status.value,
            reason=self._reason_payload(request.reason),
            provenance=request.provenance,
            execution_context=request.execution_context,
            started_at=request.started_at,
            finished_at=request.finished_at,
        )
        session.add(observation_run)
        await session.flush()
        return observation_run

    async def create_lens_run(
        self, session: AsyncSession, observation_run: ObservationRunModel, request: LensRunInput
    ) -> LensRunModel:
        """Add a pending LensRun under its authoritative ObservationRun parent."""

        lens_run = LensRunModel(
            id=request.id,
            observation_run=observation_run,
            observation_run_id=observation_run.id,
            lens_id=request.lens_id,
            lens_type=request.lens_type.value,
            status=request.status.value,
            reason=self._reason_payload(request.reason),
            provenance=request.provenance,
            execution_context=request.execution_context,
            started_at=request.started_at,
            finished_at=request.finished_at,
        )
        session.add(lens_run)
        await session.flush()
        return lens_run

    async def advance_observation_run(
        self,
        session: AsyncSession,
        observation_run: ObservationRunModel,
        target: ObservationRunStatus,
        *,
        reason: StructuredReason | None = None,
        now: datetime | None = None,
    ) -> ObservationRunModel:
        """Advance one ObservationRun through its approved lifecycle and record its reason."""

        validate_observation_run_transition(
            ObservationRunStatus(observation_run.status), target, reason
        )
        observation_run.status = target.value
        observation_run.reason = self._reason_payload(reason)
        timestamp = now or datetime.now(UTC)
        if target is ObservationRunStatus.RUNNING:
            observation_run.started_at = timestamp
        else:
            observation_run.finished_at = timestamp
        await session.flush()
        return observation_run

    async def advance_lens_run(
        self,
        session: AsyncSession,
        lens_run: LensRunModel,
        target: LensRunStatus,
        *,
        reason: StructuredReason | None = None,
        now: datetime | None = None,
    ) -> LensRunModel:
        """Advance one LensRun and preserve required partial or failure reason metadata."""

        validate_lens_run_transition(LensRunStatus(lens_run.status), target, reason)
        lens_run.status = target.value
        lens_run.reason = self._reason_payload(reason)
        timestamp = now or datetime.now(UTC)
        if target is LensRunStatus.RUNNING:
            lens_run.started_at = timestamp
        else:
            lens_run.finished_at = timestamp
        await session.flush()
        return lens_run

    async def persist_lens_analysis_result(
        self,
        session: AsyncSession,
        lens_run: LensRunModel,
        result: LensAnalysisResultInput,
    ) -> LensAnalysisResultModel:
        """Persist one eligible Lens artifact after validating its aggregate correlation.

        Failed Alert and Log runs are rejected because their absence is meaningful; a
        failed Metric artifact remains storable as non-usable traceability data.
        """

        # Avoid implicit lazy I/O when callers pass a LensRun loaded without its parent.
        observation_run = lens_run.__dict__.get("observation_run")
        if observation_run is None:
            observation_run = await session.scalar(
                select(ObservationRunModel).where(
                    ObservationRunModel.id == lens_run.observation_run_id
                )
            )
        self._validate_lens_result(lens_run, observation_run, result)
        existing_result = await session.scalar(
            select(LensAnalysisResultModel.id).where(
                LensAnalysisResultModel.lens_run_id == lens_run.id
            )
        )
        if existing_result is not None:
            raise ValueError("A LensRun can have at most one analysis result")
        analysis_result = LensAnalysisResultModel(
            lens_run=lens_run,
            lens_run_id=lens_run.id,
            result_type=result.result_type.value,
            status=result.status.value,
            schema_version=result.schema_version,
            payload=result.payload,
        )
        session.add(analysis_result)
        await session.flush()
        return analysis_result

    async def persist_relationship_evaluation(
        self,
        session: AsyncSession,
        observation_run: ObservationRunModel,
        evaluation: RelationshipEvaluationInput,
    ) -> RelationshipEvaluationModel:
        """Persist one self-contained relationship evaluation for an ObservationRun."""

        existing_evaluation = await session.scalar(
            select(RelationshipEvaluationModel.id).where(
                RelationshipEvaluationModel.observation_run_id == observation_run.id,
                RelationshipEvaluationModel.relationship_id == evaluation.relationship_id,
            )
        )
        if existing_evaluation is not None:
            raise ValueError("An ObservationRun can have at most one evaluation per relationship")
        model = RelationshipEvaluationModel(
            observation_run=observation_run,
            relationship_id=evaluation.relationship_id,
            payload=evaluation.payload,
        )
        session.add(model)
        await session.flush()
        return model

    async def persist_observation_analysis_result(
        self,
        session: AsyncSession,
        observation_run: ObservationRunModel,
        result: ObservationAnalysisResultInput,
    ) -> ObservationAnalysisResultModel:
        """Persist the optional Observation analysis artifact after identity correlation checks."""

        if result.identity.observation_id != observation_run.observation_id:
            raise ValueError("ObservationAnalysisResult observation identity does not match run")
        if result.identity.observation_run_id != observation_run.id:
            raise ValueError("ObservationAnalysisResult run identity does not match run")
        existing_result = await session.scalar(
            select(ObservationAnalysisResultModel.id).where(
                ObservationAnalysisResultModel.observation_run_id == observation_run.id
            )
        )
        if existing_result is not None:
            raise ValueError("An ObservationRun can have at most one ObservationAnalysisResult")
        model = ObservationAnalysisResultModel(
            observation_run=observation_run,
            observation_run_id=observation_run.id,
            schema_version=result.schema_version,
            payload=result.payload,
        )
        session.add(model)
        await session.flush()
        return model

    async def persist_observation_report(
        self,
        session: AsyncSession,
        observation_run: ObservationRunModel,
        analysis_result: ObservationAnalysisResultModel,
        report: ObservationReportInput,
    ) -> ObservationReportModel:
        """Persist one Markdown report only when its source analysis belongs to this run."""

        if analysis_result.observation_run_id != observation_run.id:
            raise ValueError("ObservationReport source analysis result does not match run")
        existing_report = await session.scalar(
            select(ObservationReportModel.id).where(
                ObservationReportModel.observation_analysis_result_id == analysis_result.id
            )
        )
        if existing_report is not None:
            raise ValueError("An ObservationRun can have at most one ObservationReport")
        model = ObservationReportModel(
            observation_analysis_result=analysis_result,
            observation_analysis_result_id=analysis_result.id,
            generated_at=report.generated_at,
            format=report.format,
            content=report.content,
        )
        session.add(model)
        await session.flush()
        return model

    async def get_observation_run(
        self, session: AsyncSession, observation_run_id: UUID
    ) -> ObservationRunModel | None:
        """Load a runtime aggregate with every available artifact in eager async-safe form.

        Missing results remain absent rather than becoming empty placeholders, preserving
        the failed Alert/Log distinction and early-failed ObservationRun semantics.
        """

        result = await session.scalars(
            select(ObservationRunModel)
            .where(ObservationRunModel.id == observation_run_id)
            .options(
                selectinload(ObservationRunModel.lens_runs).selectinload(
                    LensRunModel.analysis_result
                ),
                selectinload(ObservationRunModel.relationship_evaluations),
                selectinload(ObservationRunModel.observation_analysis_result).selectinload(
                    ObservationAnalysisResultModel.report
                ),
            )
        )
        return result.unique().one_or_none()

    @staticmethod
    def _reason_payload(reason: StructuredReason | None) -> dict[str, object] | None:
        """Serialize the common reason without allowing callers to mutate ORM JSON directly."""

        if reason is None:
            return None
        return reason.model_dump(mode="json")

    @staticmethod
    def _validate_lens_result(
        lens_run: LensRunModel,
        observation_run: ObservationRunModel | None,
        result: LensAnalysisResultInput,
    ) -> None:
        """Protect type, status, identity, and common partial-reason correlations.

        Parent identity is checked through the LensRun-to-ObservationRun path so a result
        cannot be attached to a contradictory runtime aggregate.
        """

        if result.result_type.value != lens_run.lens_type:
            raise ValueError("Lens analysis result type does not match LensRun type")
        if result.status.value != lens_run.status:
            raise ValueError("Lens analysis result status does not match LensRun status")
        if observation_run is None:
            raise ValueError("LensRun must be associated with an ObservationRun")
        if result.identity.observation_id != observation_run.observation_id:
            raise ValueError("Lens analysis result observation identity does not match LensRun")
        if result.identity.observation_run_id != lens_run.observation_run_id:
            raise ValueError("Lens analysis result ObservationRun identity does not match LensRun")
        if result.identity.lens_id != lens_run.lens_id:
            raise ValueError("Lens analysis result Lens identity does not match LensRun")
        if result.identity.lens_run_id != lens_run.id:
            raise ValueError("Lens analysis result LensRun identity does not match LensRun")
        if result.status is LensRunStatus.PARTIAL:
            if lens_run.reason is None:
                raise ValueError("Partial LensRun requires a structured reason")
            lens_run_reason = StructuredReason.model_validate(lens_run.reason)
            result_reason = StructuredReason.model_validate(result.payload["reason"])
            if lens_run_reason != result_reason:
                raise ValueError("Partial LensRun reason does not match LensAnalysisResult reason")
