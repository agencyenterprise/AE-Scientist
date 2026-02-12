"""Add ethical_concerns_explanation column to rp_llm_reviews.

This column stores an explanation of ethical concerns when ethical_concerns is True.
The field is non-nullable with an empty string default - it should be '' when
ethical_concerns is False, and contain an explanation string when ethical_concerns is True.

Revision ID: 0076
Revises: 0075
Create Date: 2026-02-12
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0076"
down_revision: Union[str, None] = "0075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ethical_concerns_explanation column to rp_llm_reviews."""
    # Add column as nullable first (IF NOT EXISTS for idempotency)
    op.execute(
        """
        ALTER TABLE rp_llm_reviews
        ADD COLUMN IF NOT EXISTS ethical_concerns_explanation TEXT DEFAULT ''
        """
    )
    # Backfill any NULL values to empty string
    op.execute(
        """
        UPDATE rp_llm_reviews
        SET ethical_concerns_explanation = ''
        WHERE ethical_concerns_explanation IS NULL
        """
    )
    # Now make the column NOT NULL
    op.execute(
        """
        ALTER TABLE rp_llm_reviews
        ALTER COLUMN ethical_concerns_explanation SET NOT NULL
        """
    )


def downgrade() -> None:
    """Remove ethical_concerns_explanation column."""
    op.drop_column("rp_llm_reviews", "ethical_concerns_explanation")
