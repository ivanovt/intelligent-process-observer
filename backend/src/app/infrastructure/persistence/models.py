"""SQLAlchemy storage models for definition and runtime persistence aggregates."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.infrastructure.persistence.database import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class ObservationModel(Base):
    __tablename__ = "observation_definitions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    objective: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    creation_order: Mapped[int] = mapped_column(Identity(), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lenses: Mapped[list[MetricLensModel]] = relationship(
        back_populates="observation",
        cascade="all, delete-orphan",
        order_by="MetricLensModel.position",
    )
    relationships: Mapped[list[ObservationRelationshipModel]] = relationship(
        back_populates="observation",
        cascade="all, delete-orphan",
        order_by="ObservationRelationshipModel.position",
    )


class MetricLensModel(Base):
    __tablename__ = "metric_lens_definitions"
    __table_args__ = (UniqueConstraint("observation_id", "lens_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("observation_definitions.id", ondelete="CASCADE"), nullable=False
    )
    lens_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    adapter_type: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(255))
    metric_id: Mapped[str] = mapped_column(String(255))
    query: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(255))
    analysis_objectives: Mapped[list[str]] = mapped_column(JSONType)
    reference_periods: Mapped[list[str]] = mapped_column(JSONType)
    position: Mapped[int] = mapped_column(Integer)

    observation: Mapped[ObservationModel] = relationship(back_populates="lenses")


class ObservationRelationshipModel(Base):
    __tablename__ = "observation_relationship_definitions"
    __table_args__ = (UniqueConstraint("observation_id", "relationship_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("observation_definitions.id", ondelete="CASCADE"), nullable=False
    )
    relationship_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    participants: Mapped[list[str]] = mapped_column(JSONType)
    conditions: Mapped[dict[str, object]] = mapped_column(JSONType)
    expected: Mapped[dict[str, object]] = mapped_column(JSONType)
    position: Mapped[int] = mapped_column(Integer)

    observation: Mapped[ObservationModel] = relationship(back_populates="relationships")


class ObservationRunModel(Base):
    """Durable root of one execution, kept separate from its Observation definition."""

    __tablename__ = "observation_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("observation_definitions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[dict[str, object] | None] = mapped_column(JSONType, nullable=True)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONType, default=dict)
    execution_context: Mapped[dict[str, object]] = mapped_column(JSONType, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lens_runs: Mapped[list[LensRunModel]] = relationship(
        back_populates="observation_run", cascade="all, delete-orphan"
    )
    relationship_evaluations: Mapped[list[RelationshipEvaluationModel]] = relationship(
        back_populates="observation_run", cascade="all, delete-orphan"
    )
    observation_analysis_result: Mapped[ObservationAnalysisResultModel | None] = relationship(
        back_populates="observation_run", cascade="all, delete-orphan", uselist=False
    )


class LensRunModel(Base):
    """One Lens execution within an ObservationRun.

    The unique `(observation_run_id, lens_id)` constraint prevents duplicate execution
    records while the parent foreign key supplies the authoritative Observation identity.
    """

    __tablename__ = "lens_runs"
    __table_args__ = (UniqueConstraint("observation_run_id", "lens_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    observation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("observation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lens_id: Mapped[str] = mapped_column(String(255))
    lens_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[dict[str, object] | None] = mapped_column(JSONType, nullable=True)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONType, default=dict)
    execution_context: Mapped[dict[str, object]] = mapped_column(JSONType, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    observation_run: Mapped[ObservationRunModel] = relationship(back_populates="lens_runs")
    analysis_result: Mapped[LensAnalysisResultModel | None] = relationship(
        back_populates="lens_run", cascade="all, delete-orphan", uselist=False
    )


class LensAnalysisResultModel(Base):
    """Single type-discriminated artifact produced by a LensRun.

    Its parent path provides ObservationRun correlation, avoiding a redundant column that
    could contradict the aggregate. A failed Metric result can occupy this relationship
    for traceability but is intentionally not usable downstream.
    """

    __tablename__ = "lens_analysis_results"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lens_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("lens_runs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    result_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    schema_version: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, object]] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lens_run: Mapped[LensRunModel] = relationship(back_populates="analysis_result")

    @property
    def is_usable(self) -> bool:
        return self.status in {"completed", "partial"}


class RelationshipEvaluationModel(Base):
    """Self-contained relationship evidence, unique per relationship within one run."""

    __tablename__ = "relationship_evaluations"
    __table_args__ = (UniqueConstraint("observation_run_id", "relationship_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    observation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("observation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_id: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, object]] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    observation_run: Mapped[ObservationRunModel] = relationship(
        back_populates="relationship_evaluations"
    )


class ObservationAnalysisResultModel(Base):
    """Optional, versioned Observation-level artifact with at most one report projection."""

    __tablename__ = "observation_analysis_results"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    observation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("observation_runs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    schema_version: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, object]] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    observation_run: Mapped[ObservationRunModel] = relationship(
        back_populates="observation_analysis_result"
    )
    report: Mapped[ObservationReportModel | None] = relationship(
        back_populates="observation_analysis_result", uselist=False
    )


class ObservationReportModel(Base):
    """Optional Markdown projection of exactly one ObservationAnalysisResult.

    The report derives its ObservationRun correlation through its source analysis result,
    which prevents the two aggregate paths from diverging.
    """

    __tablename__ = "observation_reports"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    observation_analysis_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("observation_analysis_results.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    format: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    observation_analysis_result: Mapped[ObservationAnalysisResultModel] = relationship(
        back_populates="report"
    )
