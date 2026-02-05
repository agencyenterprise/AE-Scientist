"""Add node_index column to code execution events table.

This column stores the 1-based node index within the stage for display purposes,
making it easier to identify nodes without relying on UUID execution IDs.

Revision ID: 0055
Revises: 0054
Create Date: 2026-02-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0055"
down_revision: Union[str, None] = "0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add node_index integer column to code execution events."""
    # Add column as nullable first
    op.add_column(
        "rp_code_execution_events",
        sa.Column("node_index", sa.Integer(), nullable=True),
    )
    # Backfill existing rows with 0 (legacy/unknown index)
    op.execute("UPDATE rp_code_execution_events SET node_index = 0 WHERE node_index IS NULL")
    # Make column NOT NULL
    op.alter_column(
        "rp_code_execution_events",
        "node_index",
        nullable=False,
    )


def downgrade() -> None:
    """Remove node_index column."""
    op.drop_column("rp_code_execution_events", "node_index")
