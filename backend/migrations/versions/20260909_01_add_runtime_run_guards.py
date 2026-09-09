"""Add active-run and frozen relationship-order persistence guards.

Revision ID: 20260909_01
Revises: 20260901_01
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_01"
down_revision: str | None = "20260901_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIVE_RUN_INDEX = "uq_observation_runs_one_active_per_observation"
_RELATIONSHIP_POSITION_CONSTRAINT = "uq_relationship_evaluations_observation_run_id_position"


def upgrade() -> None:
    """Add durable active-run exclusion and frozen RelationshipEvaluation ordering."""

    bind = op.get_bind()
    duplicate_active_observations = bind.execute(
        sa.text(
            """
            SELECT observation_id
            FROM observation_runs
            WHERE status IN ('pending', 'running')
            GROUP BY observation_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).scalar()
    if duplicate_active_observations is not None:
        raise RuntimeError(
            "Cannot add active ObservationRun exclusion: observation "
            f"{duplicate_active_observations} has multiple pending/running runs. "
            "Reconcile those runs before migrating."
        )

    op.create_index(
        _ACTIVE_RUN_INDEX,
        "observation_runs",
        ["observation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )

    op.add_column(
        "relationship_evaluations",
        sa.Column("position", sa.Integer(), nullable=True),
    )
    bind.execute(
        sa.text(
            """
            UPDATE relationship_evaluations AS evaluation
            SET position = definition.position
            FROM observation_runs AS run,
                 observation_relationship_definitions AS definition
            WHERE evaluation.observation_run_id = run.id
              AND definition.observation_id = run.observation_id
              AND definition.relationship_id = evaluation.relationship_id
            """
        )
    )
    unresolved = bind.execute(
        sa.text(
            """
            SELECT evaluation.id
            FROM relationship_evaluations AS evaluation
            WHERE evaluation.position IS NULL
            LIMIT 1
            """
        )
    ).scalar()
    if unresolved is not None:
        raise RuntimeError(
            "Cannot backfill RelationshipEvaluation position: evaluation "
            f"{unresolved} does not map uniquely to its Observation relationship definition."
        )

    invalid_ordered_run = bind.execute(
        sa.text(
            """
            SELECT observation_run_id
            FROM relationship_evaluations
            GROUP BY observation_run_id
            HAVING COUNT(*) <> COUNT(DISTINCT position)
                OR MIN(position) <> 0
                OR MAX(position) <> COUNT(*) - 1
            LIMIT 1
            """
        )
    ).scalar()
    if invalid_ordered_run is not None:
        raise RuntimeError(
            "Cannot backfill RelationshipEvaluation position: run "
            f"{invalid_ordered_run} has duplicate or non-contiguous definition positions."
        )

    op.alter_column("relationship_evaluations", "position", nullable=False)
    op.create_unique_constraint(
        _RELATIONSHIP_POSITION_CONSTRAINT,
        "relationship_evaluations",
        ["observation_run_id", "position"],
    )


def downgrade() -> None:
    """Remove only the ordering metadata and active-run defensive index added here."""

    op.drop_constraint(
        _RELATIONSHIP_POSITION_CONSTRAINT,
        "relationship_evaluations",
        type_="unique",
    )
    op.drop_column("relationship_evaluations", "position")
    op.drop_index(_ACTIVE_RUN_INDEX, table_name="observation_runs")
