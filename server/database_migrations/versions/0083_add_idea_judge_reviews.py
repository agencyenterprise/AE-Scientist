"""Add idea_judge_reviews table

Stores per-criterion LLM-as-a-judge evaluations for research ideas,
keyed by idea_id + idea_version_id. Each criterion result is stored as
JSONB so the schema can evolve without further migrations.

Revision ID: 0083
Revises: 0082
Create Date: 2026-03-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0083"
down_revision: Union[str, None] = "0082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idea_judge_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "idea_id",
            sa.Integer(),
            sa.ForeignKey("ideas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "idea_version_id",
            sa.Integer(),
            sa.ForeignKey("idea_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Per-criterion JSONB results
        sa.Column("relevance", JSONB(), nullable=False),
        sa.Column("feasibility", JSONB(), nullable=False),
        sa.Column("novelty", JSONB(), nullable=False),
        sa.Column("impact", JSONB(), nullable=False),
        # Aggregate
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("recommendation", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        # Metadata
        sa.Column("llm_model", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "idx_idea_judge_reviews_idea_id",
        "idea_judge_reviews",
        ["idea_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_idea_judge_reviews_idea_id", table_name="idea_judge_reviews")
    op.drop_table("idea_judge_reviews")
