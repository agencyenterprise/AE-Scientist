"""Add unique constraint to rp_stage_skip_windows for (run_id, stage).

Revision ID: 0040
Revises: 0039
Create Date: 2026-01-23
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint on (run_id, stage) to rp_stage_skip_windows."""
    op.create_unique_constraint(
        "uq_rp_stage_skip_windows_run_stage",
        "rp_stage_skip_windows",
        ["run_id", "stage"],
    )


def downgrade() -> None:
    """Drop unique constraint from rp_stage_skip_windows."""
    op.drop_constraint(
        "uq_rp_stage_skip_windows_run_stage",
        "rp_stage_skip_windows",
        type_="unique",
    )
