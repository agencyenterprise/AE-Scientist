"""Create rp_artifacts table

Revision ID: 0007
Revises: 0006
Create Date: 2025-12-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rp_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "run_id",
            sa.Text(),
            sa.ForeignKey("research_pipeline_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="rp_artifacts_pkey"),
    )
    op.create_index(
        "idx_rp_artifacts_run_id",
        "rp_artifacts",
        ["run_id"],
    )
    op.create_index(
        "idx_rp_artifacts_artifact_type",
        "rp_artifacts",
        ["artifact_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_rp_artifacts_artifact_type", table_name="rp_artifacts")
    op.drop_index("idx_rp_artifacts_run_id", table_name="rp_artifacts")
    op.drop_table("rp_artifacts")
