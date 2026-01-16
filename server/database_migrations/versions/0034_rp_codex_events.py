"""Create rp_codex_events table for Codex telemetry events.

Revision ID: 0034
Revises: 0033
Create Date: 2026-01-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create table storing Codex CLI telemetry events."""
    op.create_table(
        "rp_codex_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("node", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_content", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="rp_codex_events_pkey"),
    )
    op.create_index(
        "idx_rp_codex_events_run_id",
        "rp_codex_events",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_codex_events_stage",
        "rp_codex_events",
        ["stage"],
    )
    op.create_index(
        "idx_rp_codex_events_node",
        "rp_codex_events",
        ["node"],
    )


def downgrade() -> None:
    """Drop the Codex events table."""
    op.drop_index("idx_rp_codex_events_node", table_name="rp_codex_events")
    op.drop_index("idx_rp_codex_events_stage", table_name="rp_codex_events")
    op.drop_index("idx_rp_codex_events_run_id", table_name="rp_codex_events")
    op.drop_table("rp_codex_events")
