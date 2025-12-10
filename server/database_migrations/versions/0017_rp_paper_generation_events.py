"""Create table for paper generation progress events.

Revision ID: 0017
Revises: 0016
Create Date: 2025-12-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create rp_paper_generation_events table for Stage 5 progress tracking."""
    op.create_table(
        "rp_paper_generation_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("substep", sa.Text(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("step_progress", sa.Float(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="rp_paper_generation_events_pkey"),
    )
    op.create_index(
        "idx_rp_paper_generation_events_run",
        "rp_paper_generation_events",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_paper_generation_events_created",
        "rp_paper_generation_events",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop rp_paper_generation_events table."""
    op.drop_index(
        "idx_rp_paper_generation_events_created",
        table_name="rp_paper_generation_events",
    )
    op.drop_index(
        "idx_rp_paper_generation_events_run",
        table_name="rp_paper_generation_events",
    )
    op.drop_table("rp_paper_generation_events")
