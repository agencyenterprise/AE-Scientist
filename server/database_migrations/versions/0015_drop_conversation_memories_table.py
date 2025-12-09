"""Drop conversation_memories table

Revision ID: 0015
Revises: 0014
Create Date: 2025-12-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("conversation_memories")


def downgrade() -> None:
    op.create_table(
        "conversation_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("memory_source", sa.Text(), nullable=False),
        sa.Column("memories", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="conversation_memories_conversation_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="conversation_memories_pkey"),
        sa.UniqueConstraint(
            "conversation_id",
            "memory_source",
            name="conversation_memories_conversation_id_memory_source_key",
        ),
    )
