"""Add is_admin column to users table.

Revision ID: 0072
Revises: 0071
Create Date: 2026-02-11

This migration adds an is_admin boolean column to the users table,
defaulting to FALSE and NOT NULL. Admins can be set manually via SQL.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0072"
down_revision: Union[str, None] = "0071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_admin column to users table."""
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False),
    )
    # Create partial index for faster admin user lookups
    op.create_index(
        "idx_users_is_admin",
        "users",
        ["is_admin"],
        postgresql_where=sa.text("is_admin = true"),
    )


def downgrade() -> None:
    """Remove is_admin column from users table."""
    op.drop_index("idx_users_is_admin", table_name="users")
    op.drop_column("users", "is_admin")
