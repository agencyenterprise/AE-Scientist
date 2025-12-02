"""Add cost column to research pipeline runs.

Revision ID: 0009
Revises: 0008
Create Date: 2025-12-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cost column storing RunPod hourly price."""
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "cost",
            sa.Numeric(10, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    """Remove cost column."""
    op.drop_column("research_pipeline_runs", "cost")
