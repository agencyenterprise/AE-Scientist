"""Drop cost_per_hour_cents column from research_pipeline_runs.

Revision ID: 0025
Revises: 0024
Create Date: 2025-12-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop redundant cents-per-hour column."""
    op.drop_column("research_pipeline_runs", "cost_per_hour_cents")


def downgrade() -> None:
    """Re-create cents-per-hour column."""
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "cost_per_hour_cents",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
