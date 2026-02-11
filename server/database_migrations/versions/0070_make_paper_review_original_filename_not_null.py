"""Make original_filename NOT NULL in paper_reviews

The application logic always provides original_filename when creating paper reviews,
so the column should reflect this constraint.

Revision ID: 0070
Revises: 0069
Create Date: 2026-02-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0070"
down_revision: Union[str, None] = "0069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill any NULL values (should not exist, but handle defensively)
    op.execute(
        """
        UPDATE paper_reviews
        SET original_filename = 'unknown.pdf'
        WHERE original_filename IS NULL
        """
    )

    # Make the column NOT NULL
    op.alter_column(
        "paper_reviews",
        "original_filename",
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "paper_reviews",
        "original_filename",
        nullable=True,
    )
