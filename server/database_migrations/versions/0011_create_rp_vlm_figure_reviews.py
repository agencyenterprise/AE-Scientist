"""Create table storing VLM figure reviews.

Revision ID: 0011
Revises: 0010
Create Date: 2025-12-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create table for structured VLM figure reviews."""
    op.create_table(
        "rp_vlm_figure_reviews",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column(
            "run_id",
            sa.Text(),
            sa.ForeignKey("research_pipeline_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("figure_name", sa.Text(), nullable=False),
        sa.Column("img_description", sa.Text(), nullable=False),
        sa.Column("img_review", sa.Text(), nullable=False),
        sa.Column("caption_review", sa.Text(), nullable=False),
        sa.Column("figrefs_review", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="rp_vlm_figure_reviews_pkey"),
    )
    op.create_index(
        "idx_rp_vlm_figure_reviews_run_id",
        "rp_vlm_figure_reviews",
        ["run_id"],
    )


def downgrade() -> None:
    """Drop VLM figure review table."""
    op.drop_index("idx_rp_vlm_figure_reviews_run_id", table_name="rp_vlm_figure_reviews")
    op.drop_table("rp_vlm_figure_reviews")
