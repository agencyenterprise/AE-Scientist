"""Create research_pipeline_run_terminations table.

Revision ID: 0036
Revises: 0035
Create Date: 2026-01-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_pipeline_run_terminations",
        sa.Column(
            "run_id",
            sa.Text(),
            sa.ForeignKey("research_pipeline_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="requested"),
        sa.Column(
            "requested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("artifacts_uploaded_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("pod_terminated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_trigger", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("run_id", name="research_pipeline_run_terminations_pkey"),
    )
    op.create_index(
        "idx_research_pipeline_run_terminations_status",
        "research_pipeline_run_terminations",
        ["status"],
    )
    op.create_index(
        "idx_research_pipeline_run_terminations_lease_expires_at",
        "research_pipeline_run_terminations",
        ["lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_research_pipeline_run_terminations_lease_expires_at",
        table_name="research_pipeline_run_terminations",
    )
    op.drop_index(
        "idx_research_pipeline_run_terminations_status",
        table_name="research_pipeline_run_terminations",
    )
    op.drop_table("research_pipeline_run_terminations")
