"""Create rp_stage_skip_windows table for tracking skip eligibility windows.

Revision ID: 0028
Revises: 0027
Create Date: 2025-12-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create table storing when a stage became skippable (and when it stopped)."""
    op.create_table(
        "rp_stage_skip_windows",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column(
            "opened_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("opened_reason", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("closed_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="rp_stage_skip_windows_pkey"),
    )
    op.create_index(
        "idx_rp_stage_skip_windows_run",
        "rp_stage_skip_windows",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_stage_skip_windows_stage",
        "rp_stage_skip_windows",
        ["stage"],
    )


def downgrade() -> None:
    """Drop the stage skip windows table."""
    op.drop_index(
        "idx_rp_stage_skip_windows_stage",
        table_name="rp_stage_skip_windows",
    )
    op.drop_index(
        "idx_rp_stage_skip_windows_run",
        table_name="rp_stage_skip_windows",
    )
    op.drop_table("rp_stage_skip_windows")
