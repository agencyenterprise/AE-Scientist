"""Create rp_tree_viz table for tree visualizations."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rp_tree_viz",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("stage_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("viz", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("run_id", "stage_id", name="uq_rp_tree_viz_run_stage"),
    )
    op.create_index(
        "idx_rp_tree_viz_run_id",
        "rp_tree_viz",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_tree_viz_stage_id",
        "rp_tree_viz",
        ["stage_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_rp_tree_viz_stage_id", table_name="rp_tree_viz")
    op.drop_index("idx_rp_tree_viz_run_id", table_name="rp_tree_viz")
    op.drop_table("rp_tree_viz")
