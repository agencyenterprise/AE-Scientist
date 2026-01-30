"""Create paper_reviews and paper_review_token_usages tables

Revision ID: 0046
Revises: 0045
Create Date: 2026-01-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create paper_reviews table
    op.create_table(
        "paper_reviews",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # Review content (same fields as rp_llm_reviews)
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("strengths", JSONB(), nullable=True),
        sa.Column("weaknesses", JSONB(), nullable=True),
        sa.Column("originality", sa.Integer(), nullable=True),
        sa.Column("quality", sa.Integer(), nullable=True),
        sa.Column("clarity", sa.Integer(), nullable=True),
        sa.Column("significance", sa.Integer(), nullable=True),
        sa.Column("questions", JSONB(), nullable=True),
        sa.Column("limitations", JSONB(), nullable=True),
        sa.Column("ethical_concerns", sa.Boolean(), nullable=True),
        sa.Column("soundness", sa.Integer(), nullable=True),
        sa.Column("presentation", sa.Integer(), nullable=True),
        sa.Column("contribution", sa.Integer(), nullable=True),
        sa.Column("overall", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        # Metadata
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("s3_key", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_paper_reviews_user_id", "paper_reviews", ["user_id"])

    # Create paper_review_token_usages table
    op.create_table(
        "paper_review_token_usages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("paper_review_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["paper_review_id"], ["paper_reviews.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_paper_review_token_usages_review_id",
        "paper_review_token_usages",
        ["paper_review_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_paper_review_token_usages_review_id", table_name="paper_review_token_usages")
    op.drop_table("paper_review_token_usages")
    op.drop_index("idx_paper_reviews_user_id", table_name="paper_reviews")
    op.drop_table("paper_reviews")
