"""Drop service_keys table

Revision ID: 0002
Revises: 0001
Create Date: 2025-11-26

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop service_keys table and its index."""
    op.drop_index("idx_service_keys_hash", table_name="service_keys")
    op.drop_table("service_keys")


def downgrade() -> None:
    """Recreate service_keys table if needed."""
    pass
