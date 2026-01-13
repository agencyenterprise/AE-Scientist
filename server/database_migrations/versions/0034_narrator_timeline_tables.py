"""Create narrator timeline tables for event-driven state management.

Revision ID: 0034
Revises: 0033
Create Date: 2026-01-13

This migration creates two tables for the narrator architecture:
1. rp_timeline_events - Append-only log of narrative timeline events
2. rp_research_run_state - Current computed state derived from timeline events
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create narrator timeline tables."""

    # Create rp_timeline_events table (append-only event log)
    op.create_table(
        "rp_timeline_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column(
            "event_type",
            sa.Text(),
            nullable=False,
            comment="Discriminator field: stage_started, node_result, stage_completed, progress_update, paper_generation_step",
        ),
        sa.Column(
            "event_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Full timeline event as JSONB (matches Pydantic TimelineEvent schema)",
        ),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            comment="When the event occurred (from event data, not insertion time)",
        ),
        sa.Column("stage", sa.Text(), nullable=False, comment="Stage identifier for filtering"),
        sa.Column(
            "node_id", sa.Text(), nullable=True, comment="Node ID if event relates to specific node"
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When this record was inserted into the database",
        ),
        sa.PrimaryKeyConstraint("id", name="rp_timeline_events_pkey"),
        sa.UniqueConstraint("event_id", name="rp_timeline_events_event_id_key"),
        comment="Append-only log of narrative timeline events for research runs",
    )

    # Create indexes for common query patterns
    # Fast lookup of all events for a run
    op.create_index(
        "idx_rp_timeline_events_run_id",
        "rp_timeline_events",
        ["run_id"],
    )
    # Chronological ordering of events within a run
    op.create_index(
        "idx_rp_timeline_events_run_timestamp",
        "rp_timeline_events",
        ["run_id", "timestamp"],
    )
    # Filter events by type
    op.create_index(
        "idx_rp_timeline_events_event_type",
        "rp_timeline_events",
        ["event_type"],
    )
    # Fast lookup of events for a specific stage
    op.create_index(
        "idx_rp_timeline_events_stage",
        "rp_timeline_events",
        ["run_id", "stage"],
    )

    # Create rp_research_run_state table (computed state snapshot)
    op.create_table(
        "rp_research_run_state",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column(
            "state_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Current ResearchRunState computed by reducer (matches Pydantic schema)",
        ),
        sa.Column(
            "version",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Optimistic locking version (incremented on each update)",
        ),
        sa.Column(
            "last_event_id",
            sa.Text(),
            nullable=True,
            comment="ID of the last timeline event that was processed into this state",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When this state was last updated",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When this state record was first created",
        ),
        sa.PrimaryKeyConstraint("run_id", name="rp_research_run_state_pkey"),
        comment="Current computed state for each research run (derived from timeline events)",
    )

    # Create index for version-based optimistic locking
    op.create_index(
        "idx_rp_research_run_state_version",
        "rp_research_run_state",
        ["run_id", "version"],
    )


def downgrade() -> None:
    """Drop narrator timeline tables."""

    # Drop rp_research_run_state table and indexes
    op.drop_index("idx_rp_research_run_state_version", table_name="rp_research_run_state")
    op.drop_table("rp_research_run_state")

    # Drop rp_timeline_events table and indexes
    op.drop_index("idx_rp_timeline_events_stage", table_name="rp_timeline_events")
    op.drop_index("idx_rp_timeline_events_event_type", table_name="rp_timeline_events")
    op.drop_index("idx_rp_timeline_events_run_timestamp", table_name="rp_timeline_events")
    op.drop_index("idx_rp_timeline_events_run_id", table_name="rp_timeline_events")
    op.drop_table("rp_timeline_events")
