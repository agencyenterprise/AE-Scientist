"""Backfill is_seed_node and is_seed_agg_node in timeline events.

Adds is_seed_node and is_seed_agg_node to rp_timeline_events.event_data for
node_execution_started and node_execution_completed events that don't have them.

Fixes: AE-SCIENTIST-SERVER-44

Revision ID: 0067
Revises: 0066
Create Date: 2026-02-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0067"
down_revision: Union[str, None] = "0066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill is_seed_node in event_data for node_execution events
    op.execute(
        """
        UPDATE rp_timeline_events
        SET event_data = event_data || '{"is_seed_node": false}'::jsonb
        WHERE event_type IN ('node_execution_started', 'node_execution_completed')
          AND NOT (event_data ? 'is_seed_node')
    """
    )

    # Backfill is_seed_agg_node in event_data for node_execution events
    op.execute(
        """
        UPDATE rp_timeline_events
        SET event_data = event_data || '{"is_seed_agg_node": false}'::jsonb
        WHERE event_type IN ('node_execution_started', 'node_execution_completed')
          AND NOT (event_data ? 'is_seed_agg_node')
    """
    )


def downgrade() -> None:
    # Remove is_seed_node from event_data for node_execution events
    op.execute(
        """
        UPDATE rp_timeline_events
        SET event_data = event_data - 'is_seed_node'
        WHERE event_type IN ('node_execution_started', 'node_execution_completed')
          AND event_data ? 'is_seed_node'
    """
    )

    # Remove is_seed_agg_node from event_data for node_execution events
    op.execute(
        """
        UPDATE rp_timeline_events
        SET event_data = event_data - 'is_seed_agg_node'
        WHERE event_type IN ('node_execution_started', 'node_execution_completed')
          AND event_data ? 'is_seed_agg_node'
    """
    )
