"""Create telemetry tables for research pipeline events.

Revision ID: 0004
Revises: 0003
Create Date: 2025-11-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create rp_* tables that capture pipeline telemetry events."""
    op.create_table(
        "rp_run_stage_progress_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("max_iterations", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("total_nodes", sa.Integer(), nullable=False),
        sa.Column("buggy_nodes", sa.Integer(), nullable=False),
        sa.Column("good_nodes", sa.Integer(), nullable=False),
        sa.Column("best_metric", sa.Text(), nullable=True),
        sa.Column("eta_s", sa.Integer(), nullable=True),
        sa.Column("latest_iteration_time_s", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="rp_run_stage_progress_events_pkey"),
    )
    op.create_index(
        "idx_rp_run_stage_progress_events_run",
        "rp_run_stage_progress_events",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_run_stage_progress_events_stage",
        "rp_run_stage_progress_events",
        ["stage"],
    )

    op.create_table(
        "rp_run_log_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="rp_run_log_events_pkey"),
    )
    op.create_index("idx_rp_run_log_events_run", "rp_run_log_events", ["run_id"])

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


def downgrade() -> None:
    """Drop telemetry tables."""
    op.drop_index(
        "idx_rp_experiment_node_completed_events_stage",
        table_name="rp_experiment_node_completed_events",
    )
    op.drop_index(
        "idx_rp_experiment_node_completed_events_run",
        table_name="rp_experiment_node_completed_events",
    )
    op.drop_table("rp_experiment_node_completed_events")

    op.drop_index("idx_rp_run_log_events_run", table_name="rp_run_log_events")
    op.drop_table("rp_run_log_events")

    op.drop_index(
        "idx_rp_run_stage_progress_events_stage",
        table_name="rp_run_stage_progress_events",
    )
    op.drop_index(
        "idx_rp_run_stage_progress_events_run",
        table_name="rp_run_stage_progress_events",
    )
    op.drop_table("rp_run_stage_progress_events")
