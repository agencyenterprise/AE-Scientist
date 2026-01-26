"""Consolidate idea fields into markdown column, keeping title separate.

Revision ID: 0042
Revises: 0041
Create Date: 2026-01-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Consolidate structured idea fields into markdown column, keeping title separate."""

    # Add new column (nullable initially for migration)
    op.add_column(
        "idea_versions",
        sa.Column("idea_markdown", sa.Text(), nullable=True),
    )

    # Migrate data: Format as markdown with headers (title is kept in separate column)
    # Handle both JSONB arrays and ensure empty arrays display as "(none)"
    op.execute(
        """
        UPDATE idea_versions
        SET idea_markdown =
            '## Short Hypothesis' || E'\n' || short_hypothesis || E'\n\n' ||
            '## Related Work' || E'\n' || related_work || E'\n\n' ||
            '## Abstract' || E'\n' || abstract || E'\n\n' ||
            '## Experiments' || E'\n' ||
            CASE
                WHEN jsonb_array_length(experiments) > 0
                THEN (
                    SELECT string_agg('- ' || value::text, E'\n')
                    FROM jsonb_array_elements_text(experiments)
                )
                ELSE '(none)'
            END || E'\n\n' ||
            '## Expected Outcome' || E'\n' || expected_outcome || E'\n\n' ||
            '## Risk Factors and Limitations' || E'\n' ||
            CASE
                WHEN jsonb_array_length(risk_factors_and_limitations) > 0
                THEN (
                    SELECT string_agg('- ' || value::text, E'\n')
                    FROM jsonb_array_elements_text(risk_factors_and_limitations)
                )
                ELSE '(none)'
            END
    """
    )

    # Make NOT NULL after data migration
    op.alter_column("idea_versions", "idea_markdown", nullable=False)

    # Drop old columns (keep title, drop the rest)
    op.drop_column("idea_versions", "short_hypothesis")
    op.drop_column("idea_versions", "related_work")
    op.drop_column("idea_versions", "abstract")
    op.drop_column("idea_versions", "experiments")
    op.drop_column("idea_versions", "expected_outcome")
    op.drop_column("idea_versions", "risk_factors_and_limitations")


def downgrade() -> None:
    """Cannot safely downgrade - would lose markdown formatting and structure.

    Markdown-to-structured migration would require parsing markdown which is
    error-prone and would lose formatting. This is a one-way migration.
    """
    raise NotImplementedError(
        "Downgrade not supported. Markdown-to-structured migration would lose data "
        "and require complex parsing. This is a one-way migration."
    )
