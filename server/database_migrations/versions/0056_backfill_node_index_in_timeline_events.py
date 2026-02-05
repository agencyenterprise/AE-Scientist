"""Backfill node_index in timeline events JSONB data.

This migration adds the node_index field to existing timeline events
of type node_execution_started and node_execution_completed.

Revision ID: 0056
Revises: 0055
Create Date: 2026-02-05
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill node_index in rp_timeline_events JSONB for node execution events."""
    op.execute(
        """
        UPDATE rp_timeline_events
        SET event_data = event_data || '{"node_index": 0}'::jsonb
        WHERE event_type IN ('node_execution_started', 'node_execution_completed')
          AND NOT (event_data ? 'node_index')
        """
    )


def downgrade() -> None:
    """Remove node_index from timeline events JSONB."""
    op.execute(
        """
        UPDATE rp_timeline_events
        SET event_data = event_data - 'node_index'
        WHERE event_type IN ('node_execution_started', 'node_execution_completed')
        """
    )
