"""Add is_seed_node column to stage progress events table.

This column indicates whether the progress event is from seed node evaluation
during multi-seed reproducibility testing.

Revision ID: 0053
Revises: 0052
Create Date: 2026-02-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_seed_node boolean column to stage progress events."""
    op.add_column(
        "rp_run_stage_progress_events",
        sa.Column("is_seed_node", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    """Remove is_seed_node column."""
    op.drop_column("rp_run_stage_progress_events", "is_seed_node")
