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
