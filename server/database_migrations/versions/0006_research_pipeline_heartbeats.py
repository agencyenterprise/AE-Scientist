"""Add heartbeat tracking columns for research pipeline runs

Revision ID: 0006
Revises: 0005
Create Date: 2025-11-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "start_deadline_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.text("now() + interval '5 minutes'"),
        ),
    )
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "last_heartbeat_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "heartbeat_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("research_pipeline_runs", "heartbeat_failures")
    op.drop_column("research_pipeline_runs", "last_heartbeat_at")
    op.drop_column("research_pipeline_runs", "start_deadline_at")
