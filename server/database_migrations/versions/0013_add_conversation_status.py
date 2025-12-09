"""Add status column to conversations table with backfill logic.

Revision ID: 0013
Revises: 0012
Create Date: 2025-12-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add status column to conversations table with backfill logic."""
    # Step 1: Drop the conversation_dashboard_view if it exists
    conn = op.get_bind()
    conn.execute(sa.text("DROP VIEW IF EXISTS conversation_dashboard_view"))
    conn.commit()

    # Step 2: Add column with server default
    op.add_column(
        "conversations",
        sa.Column(
            "status",
            sa.String(255),
            server_default="draft",
            nullable=False,
        ),
    )

    # Step 3: Backfill existing conversations based on research pipeline runs
    # Conversations with research runs get 'with_research', others get 'draft'
    conn.execute(
        sa.text(
            """
        UPDATE conversations c
        SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM research_pipeline_runs rpr
                JOIN ideas i ON rpr.idea_id = i.id
                WHERE i.conversation_id = c.id
                LIMIT 1
            ) THEN 'with_research'
            ELSE 'draft'
        END
        WHERE status = 'draft'
    """
        )
    )
    conn.commit()


def downgrade() -> None:
    """Remove status column."""
    op.drop_column("conversations", "status")
