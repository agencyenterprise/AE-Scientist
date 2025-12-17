"""Add started_running_at to research_pipeline_runs.

Revision ID: 0024
Revises: 0023
Create Date: 2025-12-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: Union[str, Sequence[str], None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Track when a run transitions into the running state."""
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "started_running_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove the running timestamp column."""
    op.drop_column("research_pipeline_runs", "started_running_at")
