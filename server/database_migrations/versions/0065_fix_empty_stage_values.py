"""Fix empty string stage values to use first stage ID.

Empty strings in stage columns should be '1_initial_implementation' (the first stage).
This affects:
- rp_timeline_events: run_started events that had stage='' instead of a valid stage
- rp_codex_events: events from initialization (node=0) that had stage=''

Revision ID: 0065
Revises: 0064
Create Date: 2025-02-09
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0065"
down_revision: Union[str, None] = "0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default stage for events that had empty strings
DEFAULT_STAGE = "1_initial_implementation"


def upgrade() -> None:
    """Convert empty string stage values to the first stage ID."""
    # Fix rp_timeline_events (run_started events with empty stage)
    op.execute(
        f"""
        UPDATE rp_timeline_events
        SET stage = '{DEFAULT_STAGE}'
        WHERE stage = ''
        """
    )

    # Fix rp_codex_events (initialization events with empty stage)
    op.execute(
        f"""
        UPDATE rp_codex_events
        SET stage = '{DEFAULT_STAGE}'
        WHERE stage = ''
        """
    )


def downgrade() -> None:
    """Revert stage values back to empty strings (not recommended)."""
    # Note: This is a lossy downgrade - we can't know which rows originally had empty strings
    # We'll revert run_started events in timeline and node=0 events in codex
    op.execute(
        """
        UPDATE rp_timeline_events
        SET stage = ''
        WHERE event_type = 'run_started' AND stage = '1_initial_implementation'
        """
    )

    op.execute(
        """
        UPDATE rp_codex_events
        SET stage = ''
        WHERE node = 0 AND stage = '1_initial_implementation'
        """
    )
