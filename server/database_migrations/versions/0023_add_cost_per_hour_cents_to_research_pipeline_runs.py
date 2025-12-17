"""Add cost_per_hour_cents to research_pipeline_runs.

Revision ID: 0023
Revises: 0022
Create Date: 2025-12-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add integer cents/hour column and backfill from existing numeric cost."""
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "cost_per_hour_cents",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    # Backfill from legacy `cost` numeric (USD/hour). Keep it best-effort.
    op.execute(
        """
        UPDATE research_pipeline_runs
        SET cost_per_hour_cents = ROUND(cost * 100)::int
        WHERE (cost_per_hour_cents IS NULL OR cost_per_hour_cents = 0)
          AND cost IS NOT NULL
        """
    )


def downgrade() -> None:
    """Remove integer cents/hour column."""
    op.drop_column("research_pipeline_runs", "cost_per_hour_cents")
