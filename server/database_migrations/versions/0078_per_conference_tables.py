"""Create per-conference paper review tables

Revision ID: 0078
Revises: 0077
Create Date: 2026-02-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0078"
down_revision: Union[str, None] = "0077"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_review_neurips",
        sa.Column("paper_review_id", sa.BigInteger(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("strengths_and_weaknesses", sa.Text(), nullable=False),
        sa.Column("questions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("limitations", sa.Text(), nullable=False, server_default=sa.text("''::text")),
        sa.Column(
            "ethical_concerns", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "ethical_concerns_explanation",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''::text"),
        ),
        sa.Column("clarity_issues", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("quality", sa.Integer(), nullable=False),
        sa.Column("clarity", sa.Integer(), nullable=False),
        sa.Column("significance", sa.Integer(), nullable=False),
        sa.Column("originality", sa.Integer(), nullable=False),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("paper_review_id"),
        sa.ForeignKeyConstraint(["paper_review_id"], ["paper_reviews.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "paper_review_iclr",
        sa.Column("paper_review_id", sa.BigInteger(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("strengths", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("weaknesses", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("questions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("limitations", sa.Text(), nullable=False, server_default=sa.text("''::text")),
        sa.Column(
            "ethical_concerns", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "ethical_concerns_explanation",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''::text"),
        ),
        sa.Column("clarity_issues", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("soundness", sa.Integer(), nullable=False),
        sa.Column("presentation", sa.Integer(), nullable=False),
        sa.Column("contribution", sa.Integer(), nullable=False),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("paper_review_id"),
        sa.ForeignKeyConstraint(["paper_review_id"], ["paper_reviews.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "paper_review_icml",
        sa.Column("paper_review_id", sa.BigInteger(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("claims_and_evidence", sa.Text(), nullable=False),
        sa.Column("relation_to_prior_work", sa.Text(), nullable=False),
        sa.Column("other_aspects", sa.Text(), nullable=False),
        sa.Column("questions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("ethical_issues", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "ethical_issues_explanation",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''::text"),
        ),
        sa.Column("clarity_issues", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("paper_review_id"),
        sa.ForeignKeyConstraint(["paper_review_id"], ["paper_reviews.id"], ondelete="CASCADE"),
    )

    # Migrate existing completed reviews to per-conference tables
    op.execute(
        """
        INSERT INTO paper_review_neurips
            (paper_review_id, summary, strengths_and_weaknesses, questions, limitations,
             ethical_concerns, ethical_concerns_explanation, clarity_issues,
             quality, clarity, significance, originality, overall, confidence, decision)
        SELECT
            id,
            summary,
            COALESCE(strengths->>0, ''),
            COALESCE(questions, '[]'::jsonb),
            COALESCE(limitations->>0, ''),
            COALESCE(ethical_concerns, false),
            COALESCE(ethical_concerns_explanation, ''),
            COALESCE(clarity_issues, '[]'::jsonb),
            COALESCE(quality, 0),
            COALESCE(clarity, 0),
            COALESCE(significance, 0),
            COALESCE(originality, 0),
            COALESCE(overall, 0),
            COALESCE(confidence, 0),
            COALESCE(decision, '')
        FROM paper_reviews
        WHERE conference = 'neurips_2025' AND status = 'completed'
        """
    )

    op.execute(
        """
        INSERT INTO paper_review_iclr
            (paper_review_id, summary, strengths, weaknesses, questions, limitations,
             ethical_concerns, ethical_concerns_explanation, clarity_issues,
             soundness, presentation, contribution, overall, confidence, decision)
        SELECT
            id,
            summary,
            COALESCE(strengths, '[]'::jsonb),
            COALESCE(weaknesses, '[]'::jsonb),
            COALESCE(questions, '[]'::jsonb),
            COALESCE(limitations->>0, ''),
            COALESCE(ethical_concerns, false),
            COALESCE(ethical_concerns_explanation, ''),
            COALESCE(clarity_issues, '[]'::jsonb),
            COALESCE(soundness, 0),
            COALESCE(presentation, 0),
            COALESCE(contribution, 0),
            COALESCE(overall, 0),
            COALESCE(confidence, 0),
            COALESCE(decision, '')
        FROM paper_reviews
        WHERE conference = 'iclr_2025' AND status = 'completed'
        """
    )

    op.execute(
        """
        INSERT INTO paper_review_icml
            (paper_review_id, summary, claims_and_evidence, relation_to_prior_work,
             other_aspects, questions, ethical_issues, ethical_issues_explanation,
             clarity_issues, overall, decision)
        SELECT
            id,
            summary,
            COALESCE(strengths->>0, ''),
            COALESCE(strengths->>1, ''),
            COALESCE(weaknesses->>0, ''),
            COALESCE(questions, '[]'::jsonb),
            COALESCE(ethical_concerns, false),
            COALESCE(ethical_concerns_explanation, ''),
            COALESCE(clarity_issues, '[]'::jsonb),
            COALESCE(overall, 0),
            COALESCE(decision, '')
        FROM paper_reviews
        WHERE conference = 'icml' AND status = 'completed'
        """
    )

    # Drop old content columns from paper_reviews
    for col in [
        "summary",
        "strengths",
        "weaknesses",
        "originality",
        "quality",
        "clarity",
        "significance",
        "questions",
        "limitations",
        "ethical_concerns",
        "ethical_concerns_explanation",
        "soundness",
        "presentation",
        "contribution",
        "overall",
        "confidence",
        "decision",
        "clarity_issues",
    ]:
        op.drop_column("paper_reviews", col)


def downgrade() -> None:
    op.drop_table("paper_review_icml")
    op.drop_table("paper_review_iclr")
    op.drop_table("paper_review_neurips")

    op.add_column("paper_reviews", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("paper_reviews", sa.Column("strengths", JSONB(), nullable=True))
    op.add_column("paper_reviews", sa.Column("weaknesses", JSONB(), nullable=True))
    op.add_column("paper_reviews", sa.Column("originality", sa.Integer(), nullable=True))
    op.add_column("paper_reviews", sa.Column("quality", sa.Integer(), nullable=True))
    op.add_column("paper_reviews", sa.Column("clarity", sa.Integer(), nullable=True))
    op.add_column("paper_reviews", sa.Column("significance", sa.Integer(), nullable=True))
    op.add_column("paper_reviews", sa.Column("questions", JSONB(), nullable=True))
    op.add_column("paper_reviews", sa.Column("limitations", JSONB(), nullable=True))
    op.add_column("paper_reviews", sa.Column("ethical_concerns", sa.Boolean(), nullable=True))
    op.add_column(
        "paper_reviews",
        sa.Column("ethical_concerns_explanation", sa.Text(), nullable=True),
    )
    op.add_column("paper_reviews", sa.Column("soundness", sa.Integer(), nullable=True))
    op.add_column("paper_reviews", sa.Column("presentation", sa.Integer(), nullable=True))
    op.add_column("paper_reviews", sa.Column("contribution", sa.Integer(), nullable=True))
    op.add_column("paper_reviews", sa.Column("overall", sa.Integer(), nullable=True))
    op.add_column("paper_reviews", sa.Column("confidence", sa.Integer(), nullable=True))
    op.add_column("paper_reviews", sa.Column("decision", sa.Text(), nullable=True))
    op.add_column("paper_reviews", sa.Column("clarity_issues", JSONB(), nullable=True))
