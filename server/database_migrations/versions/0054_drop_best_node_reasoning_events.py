"""Drop rp_best_node_reasoning_events table - feature removed."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0054"
down_revision: Union[str, None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the best node reasoning events table."""
    op.drop_index(
        "idx_rp_best_node_reasoning_events_stage",
        table_name="rp_best_node_reasoning_events",
    )
    op.drop_index(
        "idx_rp_best_node_reasoning_events_run",
        table_name="rp_best_node_reasoning_events",
    )
    op.drop_table("rp_best_node_reasoning_events")


def downgrade() -> None:
    """Recreate the best node reasoning events table."""
    op.create_table(
        "rp_best_node_reasoning_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column(
            "run_id",
            sa.Text(),
            sa.ForeignKey("research_pipeline_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("node_id", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="rp_best_node_reasoning_events_pkey"),
    )
    op.create_index(
        "idx_rp_best_node_reasoning_events_run",
        "rp_best_node_reasoning_events",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_best_node_reasoning_events_stage",
        "rp_best_node_reasoning_events",
        ["stage"],
    )
