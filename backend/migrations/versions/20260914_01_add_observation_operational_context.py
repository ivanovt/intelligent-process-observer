"""Add optional Observation operational context.

Revision ID: 20260914_01
Revises: 20260913_01
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_01"
down_revision: str | None = "20260913_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable context without rewriting existing definitions."""
    op.add_column(
        "observation_definitions",
        sa.Column("operational_context", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove the column only when no accepted operator context would be lost."""
    retained_context = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM observation_definitions "
                "WHERE operational_context IS NOT NULL)"
            )
        )
        .scalar_one()
    )
    if retained_context:
        raise RuntimeError(
            "Cannot downgrade operational context storage while Observation definitions retain it. "
            "Remove it through an approved data migration first."
        )
    op.drop_column("observation_definitions", "operational_context")
