"""Add curated knowledge persistence and optional Observation scope.

Revision ID: 20260913_01
Revises: 20260909_01
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260913_01"
down_revision: str | None = "20260909_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APPROVED_VERSION_INDEX = "uq_knowledge_document_versions_one_approved_per_document"


class Vector1536(sa.types.UserDefinedType):
    """PostgreSQL pgvector column type without coupling migration execution to application code."""

    cache_ok = True

    def get_col_spec(self, **_: object) -> str:
        """Render the fixed MVP embedding dimension accepted by the retriever design."""
        return "vector(1536)"


def upgrade() -> None:
    """Enable pgvector and create additive curated-knowledge storage."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.add_column(
        "observation_definitions",
        sa.Column("knowledge_scope", json_type, nullable=True),
    )
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "knowledge_document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("authority", sa.String(length=32), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("source_media_type", sa.String(length=128), nullable=False),
        sa.Column("source_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("lifecycle", sa.String(length=16), nullable=False, server_default="imported"),
        sa.Column(
            "extraction_state", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column("extraction_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version > 0", name="ck_knowledge_document_versions_version_positive"),
        sa.CheckConstraint(
            "document_type IN "
            "('official_document', 'runbook', 'maintenance_guide', 'incident', 'operator_journal')",
            name="ck_knowledge_document_versions_document_type",
        ),
        sa.CheckConstraint(
            "authority IN ('official', 'internal_approved', 'operator_authored')",
            name="ck_knowledge_document_versions_authority",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('imported', 'approved', 'deprecated')",
            name="ck_knowledge_document_versions_lifecycle",
        ),
        sa.CheckConstraint(
            "extraction_state IN ('pending', 'ready', 'failed')",
            name="ck_knowledge_document_versions_extraction_state",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "version",
            name="uq_knowledge_document_versions_document_id_version",
        ),
        sa.UniqueConstraint(
            "document_id",
            "content_hash",
            name="uq_knowledge_document_versions_document_id_content_hash",
        ),
    )
    op.create_index(
        "ix_knowledge_document_versions_document_id",
        "knowledge_document_versions",
        ["document_id"],
    )
    op.create_index(
        _APPROVED_VERSION_INDEX,
        "knowledge_document_versions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("lifecycle = 'approved'"),
    )
    op.create_table(
        "knowledge_document_service_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.String(length=255), nullable=False),
        sa.Column("aliases", json_type, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "supported_versions", json_type, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["knowledge_document_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_version_id",
            "service_id",
            name="uq_knowledge_document_service_tags_version_service",
        ),
    )
    op.create_index(
        "ix_knowledge_document_service_tags_document_version_id",
        "knowledge_document_service_tags",
        ["document_version_id"],
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("page_ordinal", sa.Integer(), nullable=True),
        sa.Column("heading_path", json_type, nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', text)", persisted=True),
            nullable=False,
        ),
        sa.Column("embedding", Vector1536(), nullable=True),
        sa.CheckConstraint("ordinal > 0", name="ck_knowledge_chunks_ordinal_positive"),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["knowledge_document_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_version_id", "ordinal", name="uq_knowledge_chunks_version_ordinal"
        ),
    )
    op.create_index(
        "ix_knowledge_chunks_document_version_id",
        "knowledge_chunks",
        ["document_version_id"],
    )
    op.create_index(
        "ix_knowledge_chunks_search_vector",
        "knowledge_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove the schema only when no knowledge or scoped definition would be retained."""
    bind = op.get_bind()
    retained_knowledge = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM knowledge_documents)")
    ).scalar_one()
    retained_scope = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM observation_definitions "
            "WHERE knowledge_scope IS NOT NULL)"
        )
    ).scalar_one()
    if retained_knowledge or retained_scope:
        raise RuntimeError(
            "Cannot downgrade curated knowledge storage while knowledge records or Observation "
            "knowledge scopes are retained. Remove them through an approved data migration first."
        )

    op.drop_index("ix_knowledge_chunks_search_vector", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_version_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index(
        "ix_knowledge_document_service_tags_document_version_id",
        table_name="knowledge_document_service_tags",
    )
    op.drop_table("knowledge_document_service_tags")
    op.drop_index(_APPROVED_VERSION_INDEX, table_name="knowledge_document_versions")
    op.drop_index(
        "ix_knowledge_document_versions_document_id",
        table_name="knowledge_document_versions",
    )
    op.drop_table("knowledge_document_versions")
    op.drop_table("knowledge_documents")
    op.drop_column("observation_definitions", "knowledge_scope")
