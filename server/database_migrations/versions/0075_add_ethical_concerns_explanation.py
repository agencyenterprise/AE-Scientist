"""Add ethical_concerns_explanation column to paper_reviews.

This column stores an explanation of ethical concerns when ethical_concerns is True.
The field is nullable - it should be NULL when ethical_concerns is False, and
contain an explanation string when ethical_concerns is True.

Revision ID: 0075
Revises: 0074
Create Date: 2026-02-12
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0075"
down_revision: Union[str, None] = "0074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ethical_concerns_explanation column."""
    # Use raw SQL with IF NOT EXISTS to make migration idempotent
    # (column may already exist if added manually)
    op.execute(
        """
        ALTER TABLE paper_reviews
        ADD COLUMN IF NOT EXISTS ethical_concerns_explanation TEXT DEFAULT NULL
        """
    )


def downgrade() -> None:
    """Remove ethical_concerns_explanation column."""
    op.drop_column("paper_reviews", "ethical_concerns_explanation")
