"""Create table for sub-stage completion telemetry events.

Revision ID: 0012
Revises: 0011
Create Date: 2025-12-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create rp_substage_completed_events and drop legacy node-completed table."""
    op.create_table(
        "rp_substage_completed_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="rp_substage_completed_events_pkey"),
    )
    op.create_index(
        "idx_rp_substage_completed_events_run",
        "rp_substage_completed_events",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_substage_completed_events_stage",
        "rp_substage_completed_events",
        ["stage"],
    )

    # Drop legacy table that was never populated in practice.
    # If it exists, remove its indexes and the table itself.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "rp_experiment_node_completed_events" in inspector.get_table_names():
        op.drop_index(
            "idx_rp_experiment_node_completed_events_stage",
            table_name="rp_experiment_node_completed_events",
        )
        op.drop_index(
            "idx_rp_experiment_node_completed_events_run",
            table_name="rp_experiment_node_completed_events",
        )
        op.drop_table("rp_experiment_node_completed_events")


def downgrade() -> None:
    """Recreate legacy node-completed table and drop sub-stage table."""
    # Recreate legacy table
    op.create_table(
        "rp_experiment_node_completed_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("node_id", sa.Text(), nullable=True),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="rp_experiment_node_completed_events_pkey"),
    )
    op.create_index(
        "idx_rp_experiment_node_completed_events_run",
        "rp_experiment_node_completed_events",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_experiment_node_completed_events_stage",
        "rp_experiment_node_completed_events",
        ["stage"],
    )

    # Drop the new sub-stage table and its indexes.
    op.drop_index(
        "idx_rp_substage_completed_events_stage",
        table_name="rp_substage_completed_events",
    )
    op.drop_index(
        "idx_rp_substage_completed_events_run",
        table_name="rp_substage_completed_events",
    )
    op.drop_table("rp_substage_completed_events")
