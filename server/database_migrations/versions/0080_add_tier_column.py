"""Add tier column to paper_reviews

Revision ID: 0080
Revises: 0079
Create Date: 2026-02-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0080"
down_revision: Union[str, None] = "0079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_reviews",
        sa.Column("tier", sa.VARCHAR(), nullable=True),
    )
    # Backfill: existing reviews used the full pipeline, so mark them as premium
    op.execute("UPDATE paper_reviews SET tier = 'premium' WHERE tier IS NULL")
    op.alter_column("paper_reviews", "tier", nullable=False)


def downgrade() -> None:
    op.drop_column("paper_reviews", "tier")
