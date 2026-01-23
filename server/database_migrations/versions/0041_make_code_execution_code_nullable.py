"""Make code column nullable in rp_code_execution_events.

Revision ID: 0041
Revises: 0040
Create Date: 2026-01-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make code column nullable since completion events don't need to include code."""
    op.alter_column(
        "rp_code_execution_events",
        "code",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    """Revert code column to NOT NULL."""
    op.alter_column(
        "rp_code_execution_events",
        "code",
        existing_type=sa.Text(),
        nullable=False,
    )
