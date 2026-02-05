"""Drop eta_s and latest_iteration_time_s columns from stage progress events.

These columns were never used in the frontend and are being removed.

Revision ID: 0052
Revises: 0051
Create Date: 2026-02-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop unused eta columns from stage progress events."""
    op.drop_column("rp_run_stage_progress_events", "eta_s")
    op.drop_column("rp_run_stage_progress_events", "latest_iteration_time_s")


def downgrade() -> None:
    """Re-create eta columns."""
    op.add_column(
        "rp_run_stage_progress_events",
        sa.Column("latest_iteration_time_s", sa.Integer(), nullable=True),
    )
    op.add_column(
        "rp_run_stage_progress_events",
        sa.Column("eta_s", sa.Integer(), nullable=True),
    )
