"""Rename substage tables to stage tables.

Revision ID: 0061
Revises: 0060
Create Date: 2025-02-09
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0061"
down_revision: Union[str, None] = "0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename substage tables and indexes to stage."""
    # Rename rp_substage_completed_events -> rp_stage_completed_events
    op.rename_table("rp_substage_completed_events", "rp_stage_completed_events")
    op.execute(
        "ALTER INDEX idx_rp_substage_completed_events_run "
        "RENAME TO idx_rp_stage_completed_events_run"
    )
    op.execute(
        "ALTER INDEX idx_rp_substage_completed_events_stage "
        "RENAME TO idx_rp_stage_completed_events_stage"
    )

    # Rename rp_substage_summary_events -> rp_stage_summary_events
    op.rename_table("rp_substage_summary_events", "rp_stage_summary_events")
    op.execute(
        "ALTER INDEX idx_rp_substage_summary_events_run "
        "RENAME TO idx_rp_stage_summary_events_run"
    )
    op.execute(
        "ALTER INDEX idx_rp_substage_summary_events_stage "
        "RENAME TO idx_rp_stage_summary_events_stage"
    )


def downgrade() -> None:
    """Revert stage tables back to substage."""
    # Revert rp_stage_summary_events -> rp_substage_summary_events
    op.execute(
        "ALTER INDEX idx_rp_stage_summary_events_stage "
        "RENAME TO idx_rp_substage_summary_events_stage"
    )
    op.execute(
        "ALTER INDEX idx_rp_stage_summary_events_run "
        "RENAME TO idx_rp_substage_summary_events_run"
    )
    op.rename_table("rp_stage_summary_events", "rp_substage_summary_events")

    # Revert rp_stage_completed_events -> rp_substage_completed_events
    op.execute(
        "ALTER INDEX idx_rp_stage_completed_events_stage "
        "RENAME TO idx_rp_substage_completed_events_stage"
    )
    op.execute(
        "ALTER INDEX idx_rp_stage_completed_events_run "
        "RENAME TO idx_rp_substage_completed_events_run"
    )
    op.rename_table("rp_stage_completed_events", "rp_substage_completed_events")
