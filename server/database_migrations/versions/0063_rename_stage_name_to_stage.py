"""Rename stage_name to stage in rp_code_execution_events.

Standardizing on 'stage' as the column name for stage identifiers
across all tables for consistency.

Revision ID: 0063
Revises: 0062
Create Date: 2025-02-09
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0063"
down_revision: Union[str, None] = "0062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename stage_name column to stage in rp_code_execution_events."""
    op.alter_column(
        "rp_code_execution_events",
        "stage_name",
        new_column_name="stage",
    )


def downgrade() -> None:
    """Revert stage column back to stage_name."""
    op.alter_column(
        "rp_code_execution_events",
        "stage",
        new_column_name="stage_name",
    )
