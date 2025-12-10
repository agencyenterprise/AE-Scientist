"""Create billing tables for user wallets and Stripe sessions.

Revision ID: 0016
Revises: 0015
Create Date: 2025-12-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create billing tables and backfill wallets for existing users."""
    op.create_table(
        "billing_user_wallets",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="billing_user_wallets_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="billing_user_wallets_pkey"),
    )

    op.create_table(
        "billing_credit_transactions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "stripe_session_id",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="billing_credit_transactions_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="billing_credit_transactions_pkey"),
        sa.CheckConstraint(
            "transaction_type IN ('purchase', 'debit', 'refund', 'adjustment')",
            name="billing_credit_transactions_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'refunded', 'failed')",
            name="billing_credit_transactions_status_check",
        ),
    )
    op.create_index(
        "idx_billing_credit_transactions_user_created",
        "billing_credit_transactions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_billing_credit_transactions_pending",
        "billing_credit_transactions",
        ["status"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "billing_stripe_checkout_sessions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("stripe_session_id", sa.Text(), nullable=False),
        sa.Column("price_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.Text(), server_default="usd", nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="billing_stripe_checkout_sessions_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="billing_stripe_checkout_sessions_pkey"),
        sa.UniqueConstraint(
            "stripe_session_id",
            name="billing_stripe_checkout_sessions_session_id_key",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'completed', 'expired', 'failed')",
            name="billing_stripe_checkout_sessions_status_check",
        ),
    )

    # Backfill wallets for existing users.
    op.execute(
        """
        INSERT INTO billing_user_wallets (user_id, balance)
        SELECT id, 0 FROM users
        ON CONFLICT (user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    """Drop billing tables."""
    op.drop_table("billing_stripe_checkout_sessions")
    op.drop_index(
        "idx_billing_credit_transactions_pending",
        table_name="billing_credit_transactions",
    )
    op.drop_index(
        "idx_billing_credit_transactions_user_created",
        table_name="billing_credit_transactions",
    )
    op.drop_table("billing_credit_transactions")
    op.drop_table("billing_user_wallets")
