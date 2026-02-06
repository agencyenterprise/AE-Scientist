"""Add occurred_at column to rp_codex_events for accurate event timestamps.

Revision ID: 0060
Revises: 0059
Create Date: 2026-02-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0060"
down_revision: Union[str, None] = "0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add occurred_at column and backfill from created_at."""
    # Add column as nullable first
    op.add_column(
        "rp_codex_events",
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Backfill with created_at values
    op.execute("UPDATE rp_codex_events SET occurred_at = created_at")

    # Make column NOT NULL
    op.alter_column(
        "rp_codex_events",
        "occurred_at",
        nullable=False,
    )


def downgrade() -> None:
    """Remove occurred_at column."""
    op.drop_column("rp_codex_events", "occurred_at")
