"""Add observation definition storage.

Revision ID: 20260822_01
Revises:
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260822_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "observation_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("creation_order", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "metric_lens_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("lens_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("adapter_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("metric_id", sa.String(length=255), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=255), nullable=False),
        sa.Column("analysis_objectives", json_type, nullable=False),
        sa.Column("reference_periods", json_type, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["observation_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_id", "lens_id"),
    )
    op.create_table(
        "observation_relationship_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("participants", json_type, nullable=False),
        sa.Column("conditions", json_type, nullable=False),
        sa.Column("expected", json_type, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["observation_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_id", "relationship_id"),
    )


def downgrade() -> None:
    op.drop_table("observation_relationship_definitions")
    op.drop_table("metric_lens_definitions")
    op.drop_table("observation_definitions")
