"""Add execution_type column to code execution events table.

This column categorizes the type of execution:
- stage_goal: Regular node execution for stage goals
- seed: Seed evaluation execution
- aggregation: Seed aggregation execution
- metrics: Metrics parsing execution

Revision ID: 0057
Revises: 0056
Create Date: 2026-02-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0057"
down_revision: Union[str, None] = "0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add execution_type column and backfill based on existing data."""
    # Add column as nullable first
    op.add_column(
        "rp_code_execution_events",
        sa.Column("execution_type", sa.Text(), nullable=True),
    )

    # Backfill existing rows:
    # 1. If execution_id ends with '_metrics' -> 'metrics'
    # 2. Otherwise default to 'stage_goal' (we can't reliably determine seed/aggregation from existing data)
    op.execute(
        """
        UPDATE rp_code_execution_events
        SET execution_type = CASE
            WHEN execution_id LIKE '%_metrics' THEN 'metrics'
            ELSE 'stage_goal'
        END
        WHERE execution_type IS NULL
    """
    )

    # Make column NOT NULL
    op.alter_column(
        "rp_code_execution_events",
        "execution_type",
        nullable=False,
    )


def downgrade() -> None:
    """Remove execution_type column."""
    op.drop_column("rp_code_execution_events", "execution_type")
