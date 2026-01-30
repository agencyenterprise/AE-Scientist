"""Add webhook_token_hash to research_pipeline_runs for per-run authentication.

Revision ID: 0043
Revises: 0042
Create Date: 2026-01-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_pipeline_runs",
        sa.Column(
            "webhook_token_hash",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("research_pipeline_runs", "webhook_token_hash")
