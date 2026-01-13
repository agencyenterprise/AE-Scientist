"""Remove google_id from users table

Revision ID: 0033
Revises: 0032
Create Date: 2026-01-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove google_id column and constraint from users table."""
    # Drop unique constraint on google_id
    op.drop_constraint("users_google_id_key", "users", type_="unique")

    # Drop google_id column
    op.drop_column("users", "google_id")


def downgrade() -> None:
    """Restore google_id column and constraint to users table."""
    # Add google_id column back (nullable since we can't restore data)
    op.add_column("users", sa.Column("google_id", sa.Text(), nullable=True))

    # Restore unique constraint
    op.create_unique_constraint("users_google_id_key", "users", ["google_id"])
