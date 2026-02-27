"""Add pre-review analysis table for storing intermediate analysis results

Stores novelty search, citation check, missing references, and presentation
check results that are generated during the review pipeline.

Revision ID: 0081
Revises: 0080
Create Date: 2026-02-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0081"
down_revision: Union[str, None] = "0080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_review_analysis",
        sa.Column("paper_review_id", sa.BigInteger(), nullable=False),
        sa.Column("novelty_search", JSONB(), nullable=True),
        sa.Column("citation_check", JSONB(), nullable=True),
        sa.Column("missing_references", JSONB(), nullable=True),
        sa.Column("presentation_check", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("paper_review_id"),
        sa.ForeignKeyConstraint(["paper_review_id"], ["paper_reviews.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("paper_review_analysis")
