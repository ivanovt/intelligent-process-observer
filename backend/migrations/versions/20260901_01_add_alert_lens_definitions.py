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
    op.drop_constraint("lens_runs_observation_run_id_lens_id_key", "lens_runs", type_="unique")
    op.create_unique_constraint(
        "uq_lens_runs_observation_run_id_lens_type_lens_id",
        "lens_runs",
        ["observation_run_id", "lens_type", "lens_id"],
    )
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
        sa.ForeignKeyConstraint(
            ["observation_id"], ["observation_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_id", "lens_id"),
    )


def downgrade() -> None:
    duplicate_identity_exists = (
        op.get_bind()
        .execute(
            sa.text(
                """
            SELECT EXISTS (
                SELECT 1
                FROM lens_runs
                GROUP BY observation_run_id, lens_id
                HAVING COUNT(DISTINCT lens_type) > 1
            )
            """
            )
        )
        .scalar()
    )
    if duplicate_identity_exists:
        raise RuntimeError(
            "Cannot downgrade: lens_runs contains same-ID executions across Lens types. "
            "Remove or preserve those runs before restoring the legacy unique key."
        )

    op.drop_constraint(
        "uq_lens_runs_observation_run_id_lens_type_lens_id", "lens_runs", type_="unique"
    )
    op.create_unique_constraint(
        "lens_runs_observation_run_id_lens_id_key",
        "lens_runs",
        ["observation_run_id", "lens_id"],
    )
    op.drop_table("alert_lens_definitions")
