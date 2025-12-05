"""Remove external id from chat_summaries and imported_conversation_summaries tables

Revision ID: 0013
Revises: 0012
Create Date: 2025-12-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("chat_summaries", "external_id")
    op.drop_column("imported_conversation_summaries", "external_id")


def downgrade() -> None:
    op.add_column("chat_summaries", sa.Column("external_id", sa.Integer(), nullable=False))
    op.add_column(
        "imported_conversation_summaries", sa.Column("external_id", sa.Integer(), nullable=False)
    )
