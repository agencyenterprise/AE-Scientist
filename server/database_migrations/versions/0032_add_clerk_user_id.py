"""Add clerk_user_id to users table

Revision ID: 0032
Revises: 0031
Create Date: 2026-01-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add clerk_user_id column to users table."""
    # Add clerk_user_id column (nullable for existing users)
    op.add_column("users", sa.Column("clerk_user_id", sa.Text(), nullable=True))

    # Make google_id nullable (for Clerk-only users)
    op.alter_column("users", "google_id", nullable=True)

    # Add unique constraint on clerk_user_id
    op.create_unique_constraint("users_clerk_user_id_key", "users", ["clerk_user_id"])

    # Add index for faster lookups
    op.create_index("idx_users_clerk_id", "users", ["clerk_user_id"])


def downgrade() -> None:
    """Remove clerk_user_id column from users table."""
    op.drop_index("idx_users_clerk_id", table_name="users")
    op.drop_constraint("users_clerk_user_id_key", "users", type_="unique")
    op.alter_column("users", "google_id", nullable=False)
    op.drop_column("users", "clerk_user_id")
