"""Add conference and clarity_issues columns to paper_reviews

Revision ID: 0077
Revises: 0076
Create Date: 2026-02-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0077"
down_revision: Union[str, None] = "0076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("paper_reviews", sa.Column("conference", sa.Text(), nullable=True))
    op.add_column("paper_reviews", sa.Column("clarity_issues", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("paper_reviews", "clarity_issues")
    op.drop_column("paper_reviews", "conference")
