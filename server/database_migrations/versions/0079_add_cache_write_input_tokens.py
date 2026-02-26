"""Add cache_write_input_tokens to paper_review_token_usages

Revision ID: 0079
Revises: 0078
Create Date: 2026-02-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0079"
down_revision: Union[str, None] = "0078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_review_token_usages",
        sa.Column(
            "cache_write_input_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("paper_review_token_usages", "cache_write_input_tokens")
