"""Create research_pipeline_runs table

Revision ID: 0005
Revises: 0004
Create Date: 2025-11-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_pipeline_runs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "idea_id", sa.Integer(), sa.ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "idea_version_id",
            sa.Integer(),
            sa.ForeignKey("idea_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("pod_id", sa.Text(), nullable=True),
        sa.Column("pod_name", sa.Text(), nullable=True),
        sa.Column("gpu_type", sa.Text(), nullable=True),
        sa.Column("public_ip", sa.Text(), nullable=True),
        sa.Column("ssh_port", sa.Text(), nullable=True),
        sa.Column("pod_host_id", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
    )
    op.create_index(
        "idx_research_pipeline_runs_idea_version",
        "research_pipeline_runs",
        ["idea_id", "idea_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_research_pipeline_runs_idea_version",
        table_name="research_pipeline_runs",
    )
    op.drop_table("research_pipeline_runs")
