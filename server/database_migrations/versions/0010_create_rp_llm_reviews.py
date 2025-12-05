"""Create table storing structured LLM reviews.

Revision ID: 0010
Revises: 0009
Create Date: 2025-12-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create table for structured review responses."""
    op.create_table(
        "rp_llm_reviews",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column(
            "run_id",
            sa.Text(),
            sa.ForeignKey("research_pipeline_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "strengths",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "weaknesses",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("originality", sa.Numeric(5, 2), nullable=False),
        sa.Column("quality", sa.Numeric(5, 2), nullable=False),
        sa.Column("clarity", sa.Numeric(5, 2), nullable=False),
        sa.Column("significance", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "questions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "limitations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "ethical_concerns", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("soundness", sa.Numeric(5, 2), nullable=False),
        sa.Column("presentation", sa.Numeric(5, 2), nullable=False),
        sa.Column("contribution", sa.Numeric(5, 2), nullable=False),
        sa.Column("overall", sa.Numeric(5, 2), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="rp_llm_reviews_pkey"),
    )
    op.create_index(
        "idx_rp_llm_reviews_run_id",
        "rp_llm_reviews",
        ["run_id"],
    )


def downgrade() -> None:
    """Drop structured review table."""
    op.drop_index("idx_rp_llm_reviews_run_id", table_name="rp_llm_reviews")
    op.drop_table("rp_llm_reviews")
