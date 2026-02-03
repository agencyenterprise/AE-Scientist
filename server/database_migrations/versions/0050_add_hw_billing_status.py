"""Add hw_billing_status column to research_pipeline_runs.

This migration adds tracking for hardware billing status to handle cases where
RunPod returns empty billing data at pod termination. A retry mechanism can
then attempt to fetch the actual costs later.

Status values:
- pending: Run is still active, billing not finalized
- charged: Actual cost was charged successfully from RunPod data
- awaiting_billing_data: Pod terminated but RunPod returned empty data, needs retry
- charged_estimated: Fallback after max retries, charged based on hold amounts

Revision ID: 0050
Revises: 0049
Create Date: 2026-02-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add hw_billing_status and related columns to research_pipeline_runs."""
    # Add hw_billing_status column with check constraint
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "hw_billing_status",
            sa.String(32),
            nullable=True,
            server_default=None,
        ),
    )

    op.create_check_constraint(
        "research_pipeline_runs_hw_billing_status_check",
        "research_pipeline_runs",
        "hw_billing_status IN ('pending', 'charged', 'awaiting_billing_data', 'charged_estimated')",
    )

    # Add timestamp for last billing retry attempt
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "hw_billing_last_retry_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Add retry counter
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "hw_billing_retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # Set existing completed/cancelled/failed runs to 'charged' (assume billing was handled)
    # Set existing running/pending runs to 'pending'
    op.execute(
        """
        UPDATE research_pipeline_runs
        SET hw_billing_status = CASE
            WHEN status IN ('completed', 'cancelled', 'failed') THEN 'charged'
            WHEN status IN ('running', 'pending') THEN 'pending'
            ELSE NULL
        END
        """
    )

    # Create index for efficient querying of runs needing billing retry
    op.create_index(
        "ix_research_pipeline_runs_hw_billing_status",
        "research_pipeline_runs",
        ["hw_billing_status"],
        postgresql_where=sa.text("hw_billing_status = 'awaiting_billing_data'"),
    )


def downgrade() -> None:
    """Remove hw_billing_status and related columns."""
    op.drop_index(
        "ix_research_pipeline_runs_hw_billing_status",
        table_name="research_pipeline_runs",
    )

    op.drop_constraint(
        "research_pipeline_runs_hw_billing_status_check",
        "research_pipeline_runs",
        type_="check",
    )

    op.drop_column("research_pipeline_runs", "hw_billing_retry_count")
    op.drop_column("research_pipeline_runs", "hw_billing_last_retry_at")
    op.drop_column("research_pipeline_runs", "hw_billing_status")
