"""Add mcp_api_key column to users table

Revision ID: 0045
Revises: 0044
Create Date: 2026-01-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("mcp_api_key", sa.Text(), nullable=True),
    )
    op.create_unique_constraint(
        "users_mcp_api_key_key",
        "users",
        ["mcp_api_key"],
    )
    op.create_index(
        "idx_users_mcp_api_key",
        "users",
        ["mcp_api_key"],
    )


def downgrade() -> None:
    op.drop_index("idx_users_mcp_api_key", table_name="users")
    op.drop_constraint("users_mcp_api_key_key", "users", type_="unique")
    op.drop_column("users", "mcp_api_key")
