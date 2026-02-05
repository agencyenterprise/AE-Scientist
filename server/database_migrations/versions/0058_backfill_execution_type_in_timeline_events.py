"""Backfill execution_type in timeline events.

Adds execution_type to rp_timeline_events.event_data for node_execution_started
and node_execution_completed events that don't have it.

Revision ID: 0058
Revises: 0057
Create Date: 2026-02-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill execution_type in event_data for node_execution_started events
    op.execute(
        """
        UPDATE rp_timeline_events
        SET event_data = event_data || '{"execution_type": "stage_goal"}'::jsonb
        WHERE event_type IN ('node_execution_started', 'node_execution_completed')
          AND NOT (event_data ? 'execution_type')
    """
    )


def downgrade() -> None:
    # Remove execution_type from event_data for node_execution events
    op.execute(
        """
        UPDATE rp_timeline_events
        SET event_data = event_data - 'execution_type'
        WHERE event_type IN ('node_execution_started', 'node_execution_completed')
          AND event_data ? 'execution_type'
    """
    )
