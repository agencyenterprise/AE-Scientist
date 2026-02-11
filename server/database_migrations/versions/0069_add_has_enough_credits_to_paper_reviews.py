"""Add has_enough_credits column to paper_reviews.

This column tracks whether a user had positive balance when a paper review completed.
- NULL: review is still in progress
- TRUE: user had positive balance when review finished
- FALSE: user had zero or negative balance when review finished

When FALSE, the user cannot access full review details until they add credits.

Revision ID: 0069
Revises: 0068
Create Date: 2026-02-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0069"
down_revision: Union[str, None] = "0068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add has_enough_credits column and backfill existing completed/failed reviews."""
    op.add_column(
        "paper_reviews",
        sa.Column("has_enough_credits", sa.Boolean(), nullable=True),
    )

    # Backfill: set has_enough_credits = TRUE for all existing completed/failed reviews
    # This gives existing users full access to their historical reviews
    op.execute(
        """
        UPDATE paper_reviews
        SET has_enough_credits = TRUE
        WHERE status IN ('completed', 'failed')
        """
    )


def downgrade() -> None:
    """Remove has_enough_credits column."""
    op.drop_column("paper_reviews", "has_enough_credits")
