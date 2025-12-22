"""Create rp_code_execution_events table for code execution telemetry.

Revision ID: 0026
Revises: 0025
Create Date: 2025-12-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create table storing code execution telemetry from the research pipeline."""
    op.create_table(
        "rp_code_execution_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("execution_id", sa.Text(), nullable=False),
        sa.Column("stage_name", sa.Text(), nullable=False),
        sa.Column("run_type", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "completed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("exec_time", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="rp_code_execution_events_pkey"),
        sa.UniqueConstraint(
            "run_id",
            "execution_id",
            "run_type",
            name="uq_rp_code_execution_run_exec_type",
        ),
    )
    op.create_index(
        "idx_rp_code_execution_events_run_id",
        "rp_code_execution_events",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_code_execution_events_execution_id",
        "rp_code_execution_events",
        ["execution_id"],
    )


def downgrade() -> None:
    """Drop code execution telemetry table."""
    op.drop_index(
        "idx_rp_code_execution_events_execution_id",
        table_name="rp_code_execution_events",
    )
    op.drop_index(
        "idx_rp_code_execution_events_run_id",
        table_name="rp_code_execution_events",
    )
    op.drop_table("rp_code_execution_events")
