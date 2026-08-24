"""Add runtime persistence storage.

Revision ID: 20260823_01
Revises: 20260822_01
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260823_01"
down_revision: str | None = "20260822_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "observation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", json_type, nullable=True),
        sa.Column("provenance", json_type, nullable=False),
        sa.Column("execution_context", json_type, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["observation_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_observation_runs_observation_id", "observation_runs", ["observation_id"])
    op.create_table(
        "lens_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_run_id", sa.Uuid(), nullable=False),
        sa.Column("lens_id", sa.String(length=255), nullable=False),
        sa.Column("lens_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", json_type, nullable=True),
        sa.Column("provenance", json_type, nullable=False),
        sa.Column("execution_context", json_type, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["observation_run_id"], ["observation_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_run_id", "lens_id"),
    )
    op.create_index("ix_lens_runs_observation_run_id", "lens_runs", ["observation_run_id"])
    op.create_table(
        "lens_analysis_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lens_run_id", sa.Uuid(), nullable=False),
        sa.Column("result_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lens_run_id"], ["lens_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lens_run_id"),
    )
    op.create_table(
        "relationship_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_run_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_id", sa.String(length=255), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["observation_run_id"], ["observation_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_run_id", "relationship_id"),
    )
    op.create_index(
        "ix_relationship_evaluations_observation_run_id",
        "relationship_evaluations",
        ["observation_run_id"],
    )
    op.create_table(
        "observation_analysis_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_run_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["observation_run_id"], ["observation_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_run_id"),
    )
    op.create_table(
        "observation_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_analysis_result_id", sa.Uuid(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["observation_analysis_result_id"],
            ["observation_analysis_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_analysis_result_id"),
    )


def downgrade() -> None:
    op.drop_table("observation_reports")
    op.drop_table("observation_analysis_results")
    op.drop_index("ix_relationship_evaluations_observation_run_id", "relationship_evaluations")
    op.drop_table("relationship_evaluations")
    op.drop_table("lens_analysis_results")
    op.drop_index("ix_lens_runs_observation_run_id", "lens_runs")
    op.drop_table("lens_runs")
    op.drop_index("ix_observation_runs_observation_id", "observation_runs")
    op.drop_table("observation_runs")
