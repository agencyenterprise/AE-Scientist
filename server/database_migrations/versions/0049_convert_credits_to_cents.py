"""Convert credits to cents and add hold transaction types.

This migration converts the billing system from arbitrary "credits" to actual cents.
- Existing balances and transactions are multiplied by 5 (1 credit = 5 cents)
- Adds 'hold' and 'hold_reversal' transaction types for GPU billing
- Renames 'credits' column to 'amount_added_cents' in checkout sessions

Revision ID: 0049
Revises: 0048
Create Date: 2026-02-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert credits to cents and add hold transaction types."""
    # Convert existing wallet balances from credits to cents (1 credit = 5 cents)
    op.execute(
        """
        UPDATE billing_user_wallets
        SET balance = balance * 5
        """
    )

    # Convert existing transaction amounts from credits to cents
    op.execute(
        """
        UPDATE billing_credit_transactions
        SET amount = amount * 5
        """
    )

    # Drop the old check constraint and add new one with 'hold' and 'hold_reversal'
    op.drop_constraint(
        "billing_credit_transactions_type_check",
        "billing_credit_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "billing_credit_transactions_type_check",
        "billing_credit_transactions",
        "transaction_type IN ('purchase', 'debit', 'refund', 'adjustment', 'hold', 'hold_reversal')",
    )

    # Rename 'credits' column to 'amount_added_cents' in checkout sessions
    op.alter_column(
        "billing_stripe_checkout_sessions",
        "credits",
        new_column_name="amount_added_cents",
    )

    # Convert existing checkout session amounts from credits to cents
    op.execute(
        """
        UPDATE billing_stripe_checkout_sessions
        SET amount_added_cents = amount_added_cents * 5
        """
    )


def downgrade() -> None:
    """Revert cents back to credits."""
    # Revert checkout session amounts from cents to credits (divide by 5)
    op.execute(
        """
        UPDATE billing_stripe_checkout_sessions
        SET amount_added_cents = amount_added_cents / 5
        """
    )

    # Rename 'amount_added_cents' column back to 'credits'
    op.alter_column(
        "billing_stripe_checkout_sessions",
        "amount_added_cents",
        new_column_name="credits",
    )

    # Drop the new check constraint and restore the old one
    op.drop_constraint(
        "billing_credit_transactions_type_check",
        "billing_credit_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "billing_credit_transactions_type_check",
        "billing_credit_transactions",
        "transaction_type IN ('purchase', 'debit', 'refund', 'adjustment')",
    )

    # Revert transaction amounts from cents to credits
    op.execute(
        """
        UPDATE billing_credit_transactions
        SET amount = amount / 5
        """
    )

    # Revert wallet balances from cents to credits
    op.execute(
        """
        UPDATE billing_user_wallets
        SET balance = balance / 5
        """
    )
