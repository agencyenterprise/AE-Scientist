"""Fix timeline events unique constraint to be scoped to run_id.

Revision ID: 0071
Revises: 0070
Create Date: 2026-02-11

The previous unique constraint on event_id alone caused collisions across
different runs when using deterministic event IDs like 'stage_completed_3_creative_research'.

This migration:
1. Drops the old unique constraint on (event_id)
2. Creates a new composite unique constraint on (run_id, event_id)

This allows the same event_id to exist for different runs while still
preventing duplicate events within the same run.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0071"
down_revision: Union[str, None] = "0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change unique constraint from (event_id) to (run_id, event_id)."""
    # Drop the old unique constraint on event_id alone
    op.drop_constraint(
        "rp_timeline_events_event_id_key",
        "rp_timeline_events",
        type_="unique",
    )

    # Create new composite unique constraint on (run_id, event_id)
    op.create_unique_constraint(
        "rp_timeline_events_run_event_id_key",
        "rp_timeline_events",
        ["run_id", "event_id"],
    )


def downgrade() -> None:
    """Restore original unique constraint on event_id alone.

    Note: This may fail if there are now duplicate event_ids across runs.
    """
    # Drop the composite constraint
    op.drop_constraint(
        "rp_timeline_events_run_event_id_key",
        "rp_timeline_events",
        type_="unique",
    )

    # Restore the old unique constraint on event_id alone
    op.create_unique_constraint(
        "rp_timeline_events_event_id_key",
        "rp_timeline_events",
        ["event_id"],
    )
