"""Add audit trail table for research pipeline runs.

Revision ID: 0008
Revises: 0007
Create Date: 2025-12-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create audit event table and backfill existing runs."""
    op.create_table(
        "research_pipeline_run_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column(
            "run_id",
            sa.Text(),
            sa.ForeignKey("research_pipeline_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="research_pipeline_run_events_pkey"),
    )
    op.create_index(
        "idx_research_pipeline_run_events_run_id",
        "research_pipeline_run_events",
        ["run_id"],
    )
    op.create_index(
        "idx_research_pipeline_run_events_event_type",
        "research_pipeline_run_events",
        ["event_type"],
    )


def downgrade() -> None:
    """Drop audit event table."""
    op.drop_index(
        "idx_research_pipeline_run_events_event_type",
        table_name="research_pipeline_run_events",
    )
    op.drop_index(
        "idx_research_pipeline_run_events_run_id",
        table_name="research_pipeline_run_events",
    )
    op.drop_table("research_pipeline_run_events")
