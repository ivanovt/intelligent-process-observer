"""Async repository operations for the internal runtime persistence aggregate."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, cast, delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import joinedload, selectinload

from app.infrastructure.persistence.models import (
    AlertLensModel,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
    KnowledgeDocumentServiceTagModel,
    KnowledgeDocumentVersionModel,
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
from app.knowledge.management_contracts import (
    KNOWLEDGE_EMBEDDING_DIMENSIONS,
    ApprovedServiceCatalogEntry,
    KnowledgeChunkCreate,
    KnowledgeDocumentVersionCreate,
    KnowledgeScope,
)
from app.metrics.contracts import (
    MetricHistoryCandidate,
    MetricHistoryCandidates,
    MetricHistoryEmpty,
    MetricHistoryRead,
    MetricLensExecutionContext,
)
from app.observations.contracts import (
    AlertLensCreate,
    MetricLensCreate,
    ObservationCreate,
    RelationshipCreate,
)


@dataclass(frozen=True, slots=True)
class ObservationRunSummaryRecord:
    """One ordered runtime row and the minimum sources for a public summary."""

    observation_run: ObservationRunModel
    observation_name: str
    analysis_schema_version: str | None
    analysis_payload: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class ObservationRunDetailRecord:
    """One fully eager runtime aggregate paired only with its display name."""

    observation_run: ObservationRunModel
    observation_name: str


class KnowledgeLifecycleConflict(RuntimeError):
    """Signal that a concurrent lifecycle action changed the publication snapshot."""


_UNSET_LIFECYCLE_SNAPSHOT = object()


class ObservationRepository:
    async def create(
        self, session: AsyncSession, definition: ObservationCreate
    ) -> ObservationModel:
        observation = ObservationModel(
            name=definition.name,
            description=definition.description,
            objective=definition.objective,
            knowledge_scope=_knowledge_scope_payload(definition.knowledge_scope),
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
            alert_lenses=[
                AlertLensModel(
                    lens_id=lens.id,
                    lens_type=lens.type,
                    name=lens.name,
                    description=lens.description,
                    source=lens.source,
                    selector_query=lens.selector.query,
                    analysis_objectives=lens.analysis_objectives,
                    reference_periods=lens.reference_periods,
                    position=index,
                )
                for index, lens in enumerate(definition.alert_lenses)
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
        await session.refresh(
            observation, attribute_names=["lenses", "alert_lenses", "relationships"]
        )
        return observation

    async def list(self, session: AsyncSession) -> list[ObservationModel]:
        result = await session.scalars(
            select(ObservationModel)
            .options(
                selectinload(ObservationModel.lenses),
                selectinload(ObservationModel.alert_lenses),
                selectinload(ObservationModel.relationships),
            )
            .order_by(ObservationModel.creation_order)
        )
        return list(result.unique())

    async def get(self, session: AsyncSession, observation_id: UUID) -> ObservationModel | None:
        """Load one complete definition through a single coherent SQL statement.

        Joined eager loading gives execution initialization one PostgreSQL statement
        snapshot across the root and all owned collections. This prevents a concurrent
        replacement from exposing a mixture of old and new definition members without
        retaining a read lock that could delay runtime foreign-key persistence.
        """
        result = await session.scalars(
            select(ObservationModel)
            .where(ObservationModel.id == observation_id)
            .options(
                joinedload(ObservationModel.lenses),
                joinedload(ObservationModel.alert_lenses),
                joinedload(ObservationModel.relationships),
            )
        )
        return result.unique().one_or_none()

    async def replace(
        self,
        session: AsyncSession,
        observation_id: UUID,
        definition: ObservationCreate,
    ) -> ObservationModel | None:
        """Atomically reconcile one owned definition aggregate to its submitted snapshot."""
        result = await session.scalars(
            select(ObservationModel)
            .where(ObservationModel.id == observation_id)
            .options(
                selectinload(ObservationModel.lenses),
                selectinload(ObservationModel.alert_lenses),
                selectinload(ObservationModel.relationships),
            )
            .with_for_update(of=ObservationModel)
        )
        observation = result.unique().one_or_none()
        if observation is None:
            return None

        observation.name = definition.name
        observation.description = definition.description
        observation.objective = definition.objective
        observation.knowledge_scope = _knowledge_scope_payload(definition.knowledge_scope)
        observation.lenses = self._reconcile_metric_lenses(observation.lenses, definition.lenses)
        observation.alert_lenses = self._reconcile_alert_lenses(
            observation.alert_lenses, definition.alert_lenses
        )
        observation.relationships = self._reconcile_relationships(
            observation.relationships, definition.relationships
        )
        await session.flush()
        return observation

    @staticmethod
    def _reconcile_metric_lenses(
        current: list[MetricLensModel], desired: list[MetricLensCreate]
    ) -> list[MetricLensModel]:
        existing = {lens.lens_id: lens for lens in current}
        reconciled: list[MetricLensModel] = []
        for position, candidate in enumerate(desired):
            model = existing.get(candidate.id)
            if model is None:
                model = MetricLensModel(lens_id=candidate.id)
            model.name = candidate.name
            model.description = candidate.description
            model.adapter_type = candidate.adapter_type
            model.source_id = candidate.source_id
            model.metric_id = candidate.metric_id
            model.query = candidate.query
            model.unit = candidate.unit
            model.analysis_objectives = [
                objective.value for objective in candidate.analysis_objectives
            ]
            model.reference_periods = candidate.reference_periods
            model.position = position
            reconciled.append(model)
        return reconciled

    @staticmethod
    def _reconcile_alert_lenses(
        current: list[AlertLensModel], desired: list[AlertLensCreate]
    ) -> list[AlertLensModel]:
        existing = {lens.lens_id: lens for lens in current}
        reconciled: list[AlertLensModel] = []
        for position, candidate in enumerate(desired):
            model = existing.get(candidate.id)
            if model is None:
                model = AlertLensModel(lens_id=candidate.id)
            model.lens_type = candidate.type
            model.name = candidate.name
            model.description = candidate.description
            model.source = candidate.source
            model.selector_query = candidate.selector.query
            model.analysis_objectives = candidate.analysis_objectives
            model.reference_periods = candidate.reference_periods
            model.position = position
            reconciled.append(model)
        return reconciled

    @staticmethod
    def _reconcile_relationships(
        current: list[ObservationRelationshipModel], desired: list[RelationshipCreate]
    ) -> list[ObservationRelationshipModel]:
        existing = {relationship.relationship_id: relationship for relationship in current}
        reconciled: list[ObservationRelationshipModel] = []
        for position, candidate in enumerate(desired):
            model = existing.get(candidate.id)
            if model is None:
                model = ObservationRelationshipModel(relationship_id=candidate.id)
            model.name = candidate.name
            model.description = candidate.description
            model.participants = candidate.participants
            model.conditions = {
                key: value.model_dump(mode="json") for key, value in candidate.conditions.items()
            }
            model.expected = {
                key: value.model_dump(mode="json") for key, value in candidate.expected.items()
            }
            model.position = position
            reconciled.append(model)
        return reconciled


def _knowledge_scope_payload(scope: KnowledgeScope | None) -> dict[str, object] | None:
    """Serialize strict scope values into JSON-compatible definition metadata."""
    if scope is None:
        return None
    return {
        "service_ids": list(scope.service_ids),
        "service_version": scope.service_version,
    }


class KnowledgeRepository:
    """Persist curated knowledge documents, versions, chunks, and derived service metadata.

    All methods participate in the caller-owned transaction and never commit it. The
    API and ingestion layers therefore retain control of durable upload and publication
    boundaries.
    """

    async def create_document(
        self, session: AsyncSession, version: KnowledgeDocumentVersionCreate
    ) -> KnowledgeDocumentModel:
        """Create one document with its first immutable imported source version."""
        document = KnowledgeDocumentModel()
        document.versions.append(self._new_version(version, version_number=1))
        session.add(document)
        await session.flush()
        return document

    async def add_version(
        self,
        session: AsyncSession,
        document_id: UUID,
        version: KnowledgeDocumentVersionCreate,
    ) -> KnowledgeDocumentVersionModel:
        """Append the next immutable imported version to an existing document."""
        document = await session.scalar(
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == document_id)
            .with_for_update()
        )
        if document is None:
            raise LookupError(f"knowledge document {document_id} does not exist")
        current_version = await session.scalar(
            select(func.max(KnowledgeDocumentVersionModel.version)).where(
                KnowledgeDocumentVersionModel.document_id == document_id
            )
        )
        persisted = self._new_version(version, version_number=(current_version or 0) + 1)
        persisted.document_id = document.id
        session.add(persisted)
        await session.flush()
        return persisted

    async def get_document(
        self, session: AsyncSession, document_id: UUID
    ) -> KnowledgeDocumentModel | None:
        """Load one document with its immutable version history and derived artifacts."""
        return await session.scalar(
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == document_id)
            .options(
                selectinload(KnowledgeDocumentModel.versions).selectinload(
                    KnowledgeDocumentVersionModel.service_tags
                ),
                selectinload(KnowledgeDocumentModel.versions).selectinload(
                    KnowledgeDocumentVersionModel.chunks
                ),
            )
        )

    async def get_version(
        self, session: AsyncSession, document_id: UUID, version_number: int
    ) -> KnowledgeDocumentVersionModel | None:
        """Load one exact immutable version without substituting another version."""
        return await session.scalar(
            select(KnowledgeDocumentVersionModel)
            .where(
                KnowledgeDocumentVersionModel.document_id == document_id,
                KnowledgeDocumentVersionModel.version == version_number,
            )
            .options(
                selectinload(KnowledgeDocumentVersionModel.service_tags),
                selectinload(KnowledgeDocumentVersionModel.chunks),
            )
        )

    async def list_documents(self, session: AsyncSession) -> list[KnowledgeDocumentModel]:
        """List documents with version metadata in stable creation order."""
        result = await session.scalars(
            select(KnowledgeDocumentModel)
            .options(
                selectinload(KnowledgeDocumentModel.versions).selectinload(
                    KnowledgeDocumentVersionModel.service_tags
                )
            )
            .order_by(KnowledgeDocumentModel.created_at, KnowledgeDocumentModel.id)
        )
        return list(result.unique())

    async def replace_chunks(
        self,
        session: AsyncSession,
        document_version_id: UUID,
        chunks: Sequence[KnowledgeChunkCreate],
    ) -> tuple[KnowledgeChunkModel, ...]:
        """Replace unpublished derived chunks for an imported document version."""
        version = await session.get(KnowledgeDocumentVersionModel, document_version_id)
        if version is None:
            raise LookupError(f"knowledge document version {document_version_id} does not exist")
        if version.lifecycle != "imported":
            raise ValueError("chunks can only be replaced for an imported document version")
        ordinals = tuple(chunk.ordinal for chunk in chunks)
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("chunks must use unique ordinals")
        await session.execute(
            delete(KnowledgeChunkModel).where(
                KnowledgeChunkModel.document_version_id == document_version_id
            )
        )
        persisted = tuple(
            KnowledgeChunkModel(
                document_version_id=document_version_id,
                ordinal=chunk.ordinal,
                page_number=chunk.page_number,
                page_ordinal=chunk.page_ordinal,
                heading_path=list(chunk.heading_path) if chunk.heading_path is not None else None,
                text=chunk.text,
                embedding=list(chunk.embedding),
            )
            for chunk in chunks
        )
        session.add_all(persisted)
        await session.flush()
        return persisted

    async def begin_extraction_attempt(
        self,
        session: AsyncSession,
        document_id: UUID,
        version_number: int,
        *,
        attempt_id: UUID | None = None,
    ) -> UUID:
        """Fence one explicit extraction attempt to the supplied immutable version."""
        version = await self.get_version(session, document_id, version_number)
        if version is None:
            raise LookupError(f"knowledge document version {version_number} does not exist")
        if version.lifecycle != "imported":
            raise ValueError("only imported versions can be extracted")
        if version.extraction_state == "ready":
            raise ValueError("ready extraction results cannot be retried")
        identifier = attempt_id or uuid4()
        version.extraction_attempt_id = identifier
        version.extraction_state = "pending"
        version.extracted_text = None
        version.extraction_completed_at = None
        await session.flush()
        return identifier

    async def complete_extraction_attempt(
        self,
        session: AsyncSession,
        document_id: UUID,
        version_number: int,
        attempt_id: UUID,
        *,
        extracted_text: str | None,
        succeeded: bool,
    ) -> bool:
        """Persist derived extraction output only when its UUID is still current."""
        result = await session.execute(
            update(KnowledgeDocumentVersionModel)
            .where(
                KnowledgeDocumentVersionModel.document_id == document_id,
                KnowledgeDocumentVersionModel.version == version_number,
                KnowledgeDocumentVersionModel.lifecycle == "imported",
                KnowledgeDocumentVersionModel.extraction_attempt_id == attempt_id,
            )
            .values(
                extraction_state="ready" if succeeded else "failed",
                extracted_text=extracted_text if succeeded else None,
                extraction_completed_at=datetime.now(UTC),
            )
        )
        await session.flush()
        return result.rowcount == 1

    async def try_acquire_extraction_lock(
        self, session: AsyncSession, document_version_id: UUID
    ) -> bool:
        """Try to claim the PostgreSQL advisory lock for one extraction attempt."""
        return bool(
            await session.scalar(
                select(
                    func.pg_try_advisory_lock(func.hashtextextended(str(document_version_id), 0))
                )
            )
        )

    async def release_extraction_lock(
        self, session: AsyncSession, document_version_id: UUID
    ) -> None:
        """Release a previously acquired PostgreSQL advisory lock for one version."""
        await session.execute(
            select(func.pg_advisory_unlock(func.hashtextextended(str(document_version_id), 0)))
        )

    async def get_chunk(
        self,
        session: AsyncSession,
        document_id: UUID,
        version_number: int,
        ordinal: int,
        *,
        page_number: int | None,
    ) -> KnowledgeChunkModel | None:
        """Resolve one exact historical chunk without following active-version state."""
        statement = (
            select(KnowledgeChunkModel)
            .join(KnowledgeDocumentVersionModel)
            .where(
                KnowledgeDocumentVersionModel.document_id == document_id,
                KnowledgeDocumentVersionModel.version == version_number,
            )
        )
        if page_number is None:
            statement = statement.where(
                KnowledgeChunkModel.ordinal == ordinal,
                KnowledgeChunkModel.page_number.is_(None),
            )
        else:
            statement = statement.where(
                KnowledgeChunkModel.page_number == page_number,
                KnowledgeChunkModel.page_ordinal == ordinal,
            )
        return await session.scalar(statement)

    async def approved_version_id(self, session: AsyncSession, document_id: UUID) -> UUID | None:
        """Return the current approved identity for stale-publication detection."""
        return await session.scalar(
            select(KnowledgeDocumentVersionModel.id).where(
                KnowledgeDocumentVersionModel.document_id == document_id,
                KnowledgeDocumentVersionModel.lifecycle == "approved",
            )
        )

    async def ensure_publication_current(
        self,
        session: AsyncSession,
        document_id: UUID,
        version_number: int,
        *,
        expected_approved_version_id: UUID | None,
    ) -> KnowledgeDocumentVersionModel:
        """Lock and validate a publication snapshot before any candidate chunk mutation."""
        document = await session.scalar(
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == document_id)
            .with_for_update()
        )
        if document is None:
            raise LookupError(f"knowledge document {document_id} does not exist")
        if await self.approved_version_id(session, document_id) != expected_approved_version_id:
            raise KnowledgeLifecycleConflict("knowledge publication became stale")
        version = await session.scalar(
            select(KnowledgeDocumentVersionModel)
            .where(
                KnowledgeDocumentVersionModel.document_id == document_id,
                KnowledgeDocumentVersionModel.version == version_number,
            )
            .with_for_update()
        )
        if version is None:
            raise LookupError(f"knowledge document version {version_number} does not exist")
        if version.lifecycle != "imported" or version.extraction_state != "ready":
            raise KnowledgeLifecycleConflict("knowledge publication candidate became stale")
        return version

    async def approve_version(
        self,
        session: AsyncSession,
        document_id: UUID,
        version_number: int,
        *,
        expected_approved_version_id: UUID | None | object = _UNSET_LIFECYCLE_SNAPSHOT,
    ) -> KnowledgeDocumentVersionModel:
        """Publish one ready version and deprecate the document's previous approved version."""
        document = await session.scalar(
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == document_id)
            .with_for_update()
        )
        if document is None:
            raise LookupError(f"knowledge document {document_id} does not exist")
        current_approved_id = await self.approved_version_id(session, document_id)
        if (
            expected_approved_version_id is not _UNSET_LIFECYCLE_SNAPSHOT
            and current_approved_id != expected_approved_version_id
        ):
            raise KnowledgeLifecycleConflict("knowledge publication became stale")
        version = await session.scalar(
            select(KnowledgeDocumentVersionModel).where(
                KnowledgeDocumentVersionModel.document_id == document_id,
                KnowledgeDocumentVersionModel.version == version_number,
            )
        )
        if version is None:
            raise LookupError(f"knowledge document version {version_number} does not exist")
        if version.lifecycle != "imported":
            raise ValueError("only imported versions can be approved")
        if version.extraction_state != "ready":
            raise ValueError("only a ready extracted version can be approved")
        chunks = tuple(
            await session.scalars(
                select(KnowledgeChunkModel)
                .where(KnowledgeChunkModel.document_version_id == version.id)
                .order_by(KnowledgeChunkModel.ordinal)
                .with_for_update()
            )
        )
        self._require_complete_index(chunks)
        await session.execute(
            update(KnowledgeDocumentVersionModel)
            .where(
                KnowledgeDocumentVersionModel.document_id == document_id,
                KnowledgeDocumentVersionModel.lifecycle == "approved",
            )
            .values(lifecycle="deprecated")
        )
        version.lifecycle = "approved"
        await session.flush()
        return version

    @staticmethod
    def _require_complete_index(chunks: Sequence[KnowledgeChunkModel]) -> None:
        """Reject publication unless every persisted chunk has a complete searchable index."""
        if not chunks:
            raise ValueError("a version requires at least one indexed chunk before approval")
        for chunk in chunks:
            embedding = chunk.embedding
            if (
                not chunk.text.strip()
                or embedding is None
                or len(embedding) != KNOWLEDGE_EMBEDDING_DIMENSIONS
                or any(not isinstance(value, float) or not isfinite(value) for value in embedding)
            ):
                raise ValueError(
                    "all chunks must have non-empty text and finite 1536-dimensional embeddings"
                )

    async def deprecate_version(
        self,
        session: AsyncSession,
        document_id: UUID,
        version_number: int,
        *,
        expected_approved_version_id: UUID | None | object = _UNSET_LIFECYCLE_SNAPSHOT,
    ) -> KnowledgeDocumentVersionModel:
        """Remove one approved version from future retrieval without deleting its history."""
        document = await session.scalar(
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == document_id)
            .with_for_update()
        )
        if document is None:
            raise LookupError(f"knowledge document {document_id} does not exist")
        current_approved_id = await self.approved_version_id(session, document_id)
        if (
            expected_approved_version_id is not _UNSET_LIFECYCLE_SNAPSHOT
            and current_approved_id != expected_approved_version_id
        ):
            raise KnowledgeLifecycleConflict("knowledge lifecycle action became stale")
        version = await session.scalar(
            select(KnowledgeDocumentVersionModel).where(
                KnowledgeDocumentVersionModel.document_id == document_id,
                KnowledgeDocumentVersionModel.version == version_number,
            )
        )
        if version is None:
            raise LookupError(f"knowledge document version {version_number} does not exist")
        if version.lifecycle != "approved":
            raise ValueError("only an approved version can be deprecated")
        version.lifecycle = "deprecated"
        await session.flush()
        return version

    async def approved_service_catalog(
        self, session: AsyncSession
    ) -> tuple[ApprovedServiceCatalogEntry, ...]:
        """Derive the approved service catalog from active version-local metadata."""
        rows = await session.execute(
            select(
                KnowledgeDocumentServiceTagModel.service_id,
                KnowledgeDocumentServiceTagModel.aliases,
            )
            .join(
                KnowledgeDocumentVersionModel,
                KnowledgeDocumentVersionModel.id
                == KnowledgeDocumentServiceTagModel.document_version_id,
            )
            .where(KnowledgeDocumentVersionModel.lifecycle == "approved")
            .order_by(KnowledgeDocumentServiceTagModel.service_id)
        )
        aliases_by_service: dict[str, set[str]] = {}
        for service_id, aliases in rows:
            aliases_by_service.setdefault(service_id, set()).update(aliases)
        return tuple(
            ApprovedServiceCatalogEntry(service_id=service_id, aliases=tuple(sorted(aliases)))
            for service_id, aliases in aliases_by_service.items()
        )

    @staticmethod
    def _new_version(
        candidate: KnowledgeDocumentVersionCreate,
        *,
        version_number: int,
    ) -> KnowledgeDocumentVersionModel:
        return KnowledgeDocumentVersionModel(
            version=version_number,
            title=candidate.title,
            document_type=candidate.document_type.value,
            authority=candidate.authority.value,
            owner=candidate.owner,
            source_reference=candidate.source_reference,
            source_media_type=candidate.source_media_type,
            source_bytes=candidate.source_bytes,
            content_hash=candidate.content_hash,
            lifecycle="imported",
            extraction_state="pending",
            service_tags=[
                KnowledgeDocumentServiceTagModel(
                    service_id=tag.service_id,
                    aliases=list(tag.aliases),
                    supported_versions=list(tag.supported_versions),
                )
                for tag in candidate.service_tags
            ],
        )


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

        PostgreSQL parses the strict UTC timestamp payloads before applying the ADR-158
        cutoff and total ordering. This avoids treating mixed whole- and fractional-second
        JSON strings as lexically chronological. The query fetches only the newest
        effective lookback, then restores chronological order for the framework-neutral
        History analyzer.
        """

        payload = LensAnalysisResultModel.payload
        window_end = payload["analysis_window"]["to"].as_string()
        window_start = payload["analysis_window"]["from"].as_string()
        event_window_end = cast(window_end, DateTime(timezone=True))
        event_window_start = cast(window_start, DateTime(timezone=True))
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
                event_window_end < context.analysis_window.to,
            )
            .order_by(
                event_window_end.desc(),
                event_window_start.desc(),
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

        current = ObservationRunStatus(observation_run.status)
        validate_observation_run_transition(current, target, reason)
        timestamp = now or datetime.now(UTC)
        values: dict[str, object] = {
            "status": target.value,
            "reason": self._reason_payload(reason),
        }
        if target is ObservationRunStatus.RUNNING:
            values["started_at"] = timestamp
        else:
            values["finished_at"] = timestamp
        result = await session.execute(
            update(ObservationRunModel)
            .where(
                ObservationRunModel.id == observation_run.id,
                ObservationRunModel.status == current.value,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ValueError("ObservationRun persisted lifecycle state changed before transition")
        # Keep lifecycle writes at an explicit caller-transaction-owned flush boundary.
        # Do not mutate the loaded model until the guarded UPDATE is durable in the
        # current transaction; a failed flush must leave the in-memory state truthful.
        await session.flush()
        observation_run.status = target.value
        observation_run.reason = self._reason_payload(reason)
        if target is ObservationRunStatus.RUNNING:
            observation_run.started_at = timestamp
        else:
            observation_run.finished_at = timestamp
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
        """Advance one LensRun and preserve required terminal reason metadata."""

        current = LensRunStatus(lens_run.status)
        validate_lens_run_transition(current, target, reason)
        timestamp = now or datetime.now(UTC)
        values: dict[str, object] = {
            "status": target.value,
            "reason": self._reason_payload(reason),
        }
        if target is LensRunStatus.RUNNING:
            values["started_at"] = timestamp
        else:
            values["finished_at"] = timestamp
        result = await session.execute(
            update(LensRunModel)
            .where(
                LensRunModel.id == lens_run.id,
                LensRunModel.status == current.value,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ValueError("LensRun persisted lifecycle state changed before transition")
        # Keep lifecycle writes at an explicit caller-transaction-owned flush boundary.
        # Do not mutate the loaded model until the guarded UPDATE is durable in the
        # current transaction; a failed flush must leave the in-memory state truthful.
        await session.flush()
        lens_run.status = target.value
        lens_run.reason = self._reason_payload(reason)
        if target is LensRunStatus.RUNNING:
            lens_run.started_at = timestamp
        else:
            lens_run.finished_at = timestamp
        return lens_run

    async def cancel_observation_execution(
        self,
        session: AsyncSession,
        observation_run: ObservationRunModel,
        *,
        now: datetime | None = None,
    ) -> ObservationRunModel:
        """Terminalize one active aggregate without rewriting completed child work.

        The caller owns the surrounding transaction and must roll it back when this
        guarded operation rejects a contradictory parent terminalization.
        """

        timestamp = now or datetime.now(UTC)
        reason = StructuredReason(code="execution_cancelled")
        reason_payload = self._reason_payload(reason)
        parent_result = await session.execute(
            update(ObservationRunModel)
            .where(
                ObservationRunModel.id == observation_run.id,
                ObservationRunModel.status.in_(
                    (ObservationRunStatus.PENDING.value, ObservationRunStatus.RUNNING.value)
                ),
            )
            .values(
                status=ObservationRunStatus.CANCELLED.value,
                reason=reason_payload,
                finished_at=timestamp,
            )
            .execution_options(synchronize_session=False)
        )
        if parent_result.rowcount != 1:
            raise ValueError("ObservationRun persisted lifecycle state changed before cancellation")

        await session.execute(
            update(LensRunModel)
            .where(
                LensRunModel.observation_run_id == observation_run.id,
                LensRunModel.status.in_((LensRunStatus.PENDING.value, LensRunStatus.RUNNING.value)),
            )
            .values(
                status=LensRunStatus.CANCELLED.value,
                reason=reason_payload,
                finished_at=timestamp,
            )
            .execution_options(synchronize_session=False)
        )
        observation_run.status = ObservationRunStatus.CANCELLED.value
        observation_run.reason = reason_payload
        observation_run.finished_at = timestamp
        return observation_run

    async def persist_lens_analysis_result(
        self,
        session: AsyncSession,
        lens_run: LensRunModel,
        result: LensAnalysisResultInput,
    ) -> LensAnalysisResultModel:
        """Persist one eligible Lens artifact after validating its aggregate correlation.

        Failed Alert and Log runs are rejected because their absence is meaningful; a
        failed Metric artifact remains storable as non-usable traceability data. A
        cancelled LensRun cannot receive an artifact.
        """

        # Avoid implicit lazy I/O when callers pass a LensRun loaded without its parent.
        observation_run = lens_run.__dict__.get("observation_run")
        if observation_run is None:
            observation_run = await session.scalar(
                select(ObservationRunModel).where(
                    ObservationRunModel.id == lens_run.observation_run_id
                )
            )
        await session.refresh(
            lens_run,
            attribute_names=["status", "reason"],
            with_for_update=True,
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
            observation_run_id=observation_run.id,
            relationship_id=evaluation.relationship_id,
            position=evaluation.position,
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
        the failed Alert/Log distinction, cancelled LensRuns, and terminal ObservationRun
        semantics. Previously committed child and Observation-level artifacts remain loaded.
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

    async def list_observation_run_summaries(
        self, session: AsyncSession
    ) -> list[ObservationRunSummaryRecord]:
        """Load every run summary source in one newest-first SQL statement.

        The analytical payload remains deliberately unprojected here.  The public
        boundary validates its complete domain contract before it derives the
        optional analytical state.
        """

        result = await session.execute(
            select(
                ObservationRunModel,
                ObservationModel.name,
                ObservationAnalysisResultModel.schema_version,
                ObservationAnalysisResultModel.payload,
            )
            .join(ObservationModel, ObservationModel.id == ObservationRunModel.observation_id)
            .outerjoin(
                ObservationAnalysisResultModel,
                ObservationAnalysisResultModel.observation_run_id == ObservationRunModel.id,
            )
            .order_by(ObservationRunModel.created_at.desc(), ObservationRunModel.id.desc())
        )
        return [
            ObservationRunSummaryRecord(
                observation_run=row[0],
                observation_name=row[1],
                analysis_schema_version=row[2],
                analysis_payload=row[3],
            )
            for row in result
        ]

    async def get_observation_run_detail(
        self, session: AsyncSession, observation_run_id: UUID
    ) -> ObservationRunDetailRecord | None:
        """Load one full runtime graph with its Observation display identity.

        Callers that require a coherent public response must issue this loader
        inside the PostgreSQL repeatable-read transaction owned by the read
        boundary.  The select-in eager loads are then pinned to that one MVCC
        snapshot while retaining the existing aggregate ownership.
        """

        result = await session.execute(
            select(ObservationRunModel, ObservationModel.name)
            .join(ObservationModel, ObservationModel.id == ObservationRunModel.observation_id)
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
        row = result.unique().one_or_none()
        if row is None:
            return None
        return ObservationRunDetailRecord(observation_run=row[0], observation_name=row[1])

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

        if lens_run.status == LensRunStatus.CANCELLED.value:
            raise ValueError("Cancelled LensRun cannot have an analysis result")
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


class RuntimeExecutionStateStore:
    """Provide durable active-run lookup and cancellation reconciliation to the manager."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        runtime_repository: RuntimePersistenceRepository,
    ) -> None:
        self._session_factory = session_factory
        self._runtime_repository = runtime_repository

    async def get_active_observation_run_id(self, observation_id: UUID) -> UUID | None:
        """Return one deterministic active run identity for an Observation, if present."""

        async with self._session_factory() as session:
            return await session.scalar(
                select(ObservationRunModel.id)
                .where(
                    ObservationRunModel.observation_id == observation_id,
                    ObservationRunModel.status.in_(
                        (ObservationRunStatus.PENDING.value, ObservationRunStatus.RUNNING.value)
                    ),
                )
                .order_by(ObservationRunModel.created_at.desc(), ObservationRunModel.id.desc())
                .limit(1)
            )

    async def reconcile_active_observation_runs(self) -> None:
        """Atomically cancel every durable active aggregate without altering terminal artifacts."""

        async with self._session_factory.begin() as session:
            active_runs = list(
                await session.scalars(
                    select(ObservationRunModel)
                    .where(
                        ObservationRunModel.status.in_(
                            (ObservationRunStatus.PENDING.value, ObservationRunStatus.RUNNING.value)
                        )
                    )
                    .order_by(ObservationRunModel.created_at, ObservationRunModel.id)
                )
            )
            for observation_run in active_runs:
                await self._runtime_repository.cancel_observation_execution(
                    session, observation_run
                )

    async def has_active_observation_runs(self) -> bool:
        """Return whether durable active ObservationRuns remain after reconciliation."""

        async with self._session_factory() as session:
            return bool(
                await session.scalar(
                    select(
                        exists().where(
                            ObservationRunModel.status.in_(
                                (
                                    ObservationRunStatus.PENDING.value,
                                    ObservationRunStatus.RUNNING.value,
                                )
                            )
                        )
                    )
                )
            )
