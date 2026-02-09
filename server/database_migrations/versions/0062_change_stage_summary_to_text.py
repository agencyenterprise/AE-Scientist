"""Change stage summary from JSON to TEXT.

The summary column previously stored a JSON dict with multiple fields.
Now it only stores the transition_summary string directly.

Revision ID: 0062
Revises: 0061
Create Date: 2025-02-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0062"
down_revision: Union[str, None] = "0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert summary column from JSON to TEXT, extracting transition_summary."""
    # Add a new text column
    op.add_column(
        "rp_stage_summary_events",
        sa.Column("summary_text", sa.Text(), nullable=True),
    )

    # Extract transition_summary from JSON and populate the new column
    # Falls back to llm_summary if transition_summary is not present
    op.execute(
        """
        UPDATE rp_stage_summary_events
        SET summary_text = COALESCE(
            summary->>'transition_summary',
            summary->>'llm_summary',
            ''
        )
    """
    )

    # Drop the old JSON column
    op.drop_column("rp_stage_summary_events", "summary")

    # Rename the new column to summary
    op.alter_column(
        "rp_stage_summary_events",
        "summary_text",
        new_column_name="summary",
        nullable=False,
    )


def downgrade() -> None:
    """Convert summary column from TEXT back to JSON."""
    # Add a new JSON column
    op.add_column(
        "rp_stage_summary_events",
        sa.Column("summary_json", sa.JSON(), nullable=True),
    )

    # Convert text back to JSON with transition_summary key
    op.execute(
        """
        UPDATE rp_stage_summary_events
        SET summary_json = jsonb_build_object('transition_summary', summary)
    """
    )

    # Drop the old text column
    op.drop_column("rp_stage_summary_events", "summary")

    # Rename the new column to summary
    op.alter_column(
        "rp_stage_summary_events",
        "summary_json",
        new_column_name="summary",
        nullable=False,
    )
