"""Add table for research pipeline sub-stage summaries."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create rp_substage_summary_events table."""
    op.create_table(
        "rp_substage_summary_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            sa.Text(),
            sa.ForeignKey("research_pipeline_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_rp_substage_summary_events_run",
        "rp_substage_summary_events",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_substage_summary_events_stage",
        "rp_substage_summary_events",
        ["stage"],
    )


def downgrade() -> None:
    """Drop rp_substage_summary_events table."""
    op.drop_index(
        "idx_rp_substage_summary_events_stage",
        table_name="rp_substage_summary_events",
    )
    op.drop_index(
        "idx_rp_substage_summary_events_run",
        table_name="rp_substage_summary_events",
    )
    op.drop_table("rp_substage_summary_events")
