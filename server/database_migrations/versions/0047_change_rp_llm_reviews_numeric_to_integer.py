"""Change rp_llm_reviews numeric columns to integer

Revision ID: 0047
Revises: 0046
Create Date: 2026-01-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Columns to convert from NUMERIC(5,2) to INTEGER
NUMERIC_COLUMNS = [
    "originality",
    "quality",
    "clarity",
    "significance",
    "soundness",
    "presentation",
    "contribution",
    "overall",
    "confidence",
]


def upgrade() -> None:
    """Convert numeric columns to integer, rounding existing values."""
    for col in NUMERIC_COLUMNS:
        # First update existing data to rounded integers
        op.execute(f"UPDATE rp_llm_reviews SET {col} = ROUND({col})")
        # Then alter column type
        op.execute(
            f"ALTER TABLE rp_llm_reviews ALTER COLUMN {col} TYPE INTEGER USING {col}::INTEGER"
        )


def downgrade() -> None:
    """Convert integer columns back to numeric."""
    for col in NUMERIC_COLUMNS:
        op.execute(
            f"ALTER TABLE rp_llm_reviews ALTER COLUMN {col} TYPE NUMERIC(5,2) USING {col}::NUMERIC(5,2)"
        )
