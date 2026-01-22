"""Add parent_run_id to conversations table

Revision ID: 0039
Revises: 0038
Create Date: 2026-01-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add parent_run_id column to conversations table
    op.add_column(
        "conversations",
        sa.Column(
            "parent_run_id",
            sa.Text(),
            nullable=True,
        ),
    )

    # Add foreign key constraint to research_pipeline_runs
    op.create_foreign_key(
        "conversations_parent_run_id_fkey",
        "conversations",
        "research_pipeline_runs",
        ["parent_run_id"],
        ["run_id"],
        ondelete="SET NULL",
    )

    # Create index for parent_run_id lookups
    op.create_index(
        "idx_conversations_parent_run_id",
        "conversations",
        ["parent_run_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_conversations_parent_run_id", table_name="conversations")
    op.drop_constraint("conversations_parent_run_id_fkey", "conversations", type_="foreignkey")
    op.drop_column("conversations", "parent_run_id")
