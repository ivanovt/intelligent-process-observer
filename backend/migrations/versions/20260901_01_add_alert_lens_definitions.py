"""Add Alert Lens definition storage.

Revision ID: 20260901_01
Revises: 20260823_01
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260901_01"
down_revision: str | None = "20260823_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "alert_lens_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("lens_id", sa.String(length=255), nullable=False),
        sa.Column("lens_type", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("selector_query", sa.Text(), nullable=False),
        sa.Column("analysis_objectives", json_type, nullable=False),
        sa.Column("reference_periods", json_type, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["observation_id"], ["observation_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_id", "lens_id"),
    )


def downgrade() -> None:
    op.drop_table("alert_lens_definitions")
