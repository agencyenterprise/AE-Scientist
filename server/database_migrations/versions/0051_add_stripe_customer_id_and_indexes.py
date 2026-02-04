"""Add stripe_customer_id to users and billing indexes

Revision ID: 0051
Revises: 0050
Create Date: 2026-02-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add stripe_customer_id column to users table
    op.add_column(
        "users",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    )
    # Partial index for faster Stripe customer lookups (only non-null values)
    op.create_index(
        "idx_users_stripe_customer_id",
        "users",
        ["stripe_customer_id"],
        postgresql_where=sa.text("stripe_customer_id IS NOT NULL"),
    )

    # Add composite index for credit transactions (user_id + transaction_type)
    # Optimizes filtered queries in list_credit_transactions
    op.create_index(
        "idx_credit_transactions_user_type",
        "billing_credit_transactions",
        ["user_id", "transaction_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_credit_transactions_user_type",
        table_name="billing_credit_transactions",
    )
    op.drop_index("idx_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "stripe_customer_id")
