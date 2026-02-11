"""Add has_enough_credits column to research_pipeline_runs.

This column tracks whether a user had positive balance when a run completed.
- NULL: run is still in progress
- TRUE: user had positive balance when run finished
- FALSE: user had zero or negative balance when run finished

When FALSE, the user cannot access full run details until they add credits.

Revision ID: 0068
Revises: 0067
Create Date: 2026-02-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0068"
down_revision: Union[str, None] = "0067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add has_enough_credits column and backfill existing completed/failed runs."""
    op.add_column(
        "research_pipeline_runs",
        sa.Column("has_enough_credits", sa.Boolean(), nullable=True),
    )

    # Backfill: set has_enough_credits = TRUE for all existing completed/failed runs
    # This gives existing users full access to their historical runs
    op.execute(
        """
        UPDATE research_pipeline_runs
        SET has_enough_credits = TRUE
        WHERE status IN ('completed', 'failed')
        """
    )


def downgrade() -> None:
    """Remove has_enough_credits column."""
    op.drop_column("research_pipeline_runs", "has_enough_credits")
