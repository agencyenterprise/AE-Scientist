"""Split NeurIPS strengths_and_weaknesses into separate strengths and weaknesses columns

The combined text field is replaced by two JSONB array columns matching
the ICLR schema pattern.

Existing data is migrated by wrapping the combined text in a single-element array
for the strengths column, with an empty array for weaknesses.

Revision ID: 0082
Revises: 0081
Create Date: 2026-03-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0082"
down_revision: Union[str, None] = "0081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_review_neurips",
        sa.Column("strengths", JSONB(), nullable=True),
    )
    op.add_column(
        "paper_review_neurips",
        sa.Column("weaknesses", JSONB(), nullable=True),
    )

    # Migrate existing data: put the combined text as a single element in strengths
    op.execute(
        """
        UPDATE paper_review_neurips
        SET strengths = jsonb_build_array(strengths_and_weaknesses),
            weaknesses = '[]'::jsonb
        WHERE strengths_and_weaknesses IS NOT NULL
        """
    )

    # Set defaults for any NULLs (shouldn't exist, but be safe)
    op.execute(
        """
        UPDATE paper_review_neurips
        SET strengths = '[]'::jsonb
        WHERE strengths IS NULL
        """
    )
    op.execute(
        """
        UPDATE paper_review_neurips
        SET weaknesses = '[]'::jsonb
        WHERE weaknesses IS NULL
        """
    )

    # Make columns non-nullable with defaults
    op.alter_column(
        "paper_review_neurips",
        "strengths",
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    op.alter_column(
        "paper_review_neurips",
        "weaknesses",
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )

    op.drop_column("paper_review_neurips", "strengths_and_weaknesses")


def downgrade() -> None:
    op.add_column(
        "paper_review_neurips",
        sa.Column("strengths_and_weaknesses", sa.Text(), nullable=True),
    )

    # Concatenate strengths array elements back into a single text field
    op.execute(
        """
        UPDATE paper_review_neurips
        SET strengths_and_weaknesses = (
            SELECT string_agg(elem, E'\n')
            FROM jsonb_array_elements_text(strengths) AS elem
        )
        """
    )

    op.execute(
        """
        UPDATE paper_review_neurips
        SET strengths_and_weaknesses = ''
        WHERE strengths_and_weaknesses IS NULL
        """
    )

    op.alter_column(
        "paper_review_neurips",
        "strengths_and_weaknesses",
        nullable=False,
        server_default=sa.text("''::text"),
    )

    op.drop_column("paper_review_neurips", "weaknesses")
    op.drop_column("paper_review_neurips", "strengths")
