"""Add status and error_message columns to paper_reviews

Revision ID: 0048
Revises: 0047
Create Date: 2026-02-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add status column with default 'completed' for existing rows
    op.add_column(
        "paper_reviews",
        sa.Column(
            "status",
            sa.Text(),
            server_default="completed",
            nullable=False,
        ),
    )

    # Add error_message column for failed reviews
    op.add_column(
        "paper_reviews",
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    # Add index for efficient lookup of user's pending reviews
    op.create_index(
        "idx_paper_reviews_user_id_status",
        "paper_reviews",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_paper_reviews_user_id_status", table_name="paper_reviews")
    op.drop_column("paper_reviews", "error_message")
    op.drop_column("paper_reviews", "status")
