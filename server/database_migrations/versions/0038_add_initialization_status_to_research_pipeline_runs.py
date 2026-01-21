"""Add initialization_status to research_pipeline_runs.

Revision ID: 0038
Revises: 0037
Create Date: 2026-01-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "initialization_status",
            sa.Text(),
            nullable=False,
            server_default="pending",
        ),
    )


def downgrade() -> None:
    op.drop_column("research_pipeline_runs", "initialization_status")
