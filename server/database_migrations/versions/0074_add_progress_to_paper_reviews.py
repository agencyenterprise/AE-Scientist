"""Add progress columns to paper_reviews.

These columns track the progress of paper reviews while they are being processed.
- progress: Float between 0.0 and 1.0 indicating overall completion percentage
- progress_step: Text description of the current step (e.g., "Review 2 of 3")

For completed/failed reviews, progress is 1.0 and progress_step is empty.
For pending reviews, progress starts at 0.0.

Revision ID: 0074
Revises: 0073
Create Date: 2026-02-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0074"
down_revision: Union[str, None] = "0073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add progress and progress_step columns with backfill."""
    # Add columns as nullable first
    op.add_column(
        "paper_reviews",
        sa.Column("progress", sa.Float(), nullable=True),
    )
    op.add_column(
        "paper_reviews",
        sa.Column("progress_step", sa.Text(), nullable=True),
    )

    # Backfill: completed/failed reviews get progress=1.0, pending/processing get 0.0
    op.execute(
        """
        UPDATE paper_reviews
        SET progress = CASE
            WHEN status IN ('completed', 'failed') THEN 1.0
            ELSE 0.0
        END,
        progress_step = ''
        """
    )

    # Now make columns NOT NULL
    op.alter_column("paper_reviews", "progress", nullable=False)
    op.alter_column("paper_reviews", "progress_step", nullable=False)


def downgrade() -> None:
    """Remove progress columns."""
    op.drop_column("paper_reviews", "progress_step")
    op.drop_column("paper_reviews", "progress")
