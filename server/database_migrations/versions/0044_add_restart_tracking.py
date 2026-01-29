"""Add restart tracking columns for research pipeline runs

Revision ID: 0044
Revises: 0043
Create Date: 2026-01-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "restart_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "last_restart_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "last_restart_reason",
            sa.String(100),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("research_pipeline_runs", "last_restart_reason")
    op.drop_column("research_pipeline_runs", "last_restart_at")
    op.drop_column("research_pipeline_runs", "restart_count")
