"""Create billing_pending_credits table for pre-registration credits.

Revision ID: 0073
Revises: 0072
Create Date: 2026-02-11

This table stores credits granted to email addresses that haven't registered yet.
When a user registers with a matching email, the credits are automatically claimed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0073"
down_revision: Union[str, None] = "0072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create billing_pending_credits table."""
    op.create_table(
        "billing_pending_credits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("granted_by_user_id", sa.Integer(), nullable=False),
        sa.Column("claimed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("claimed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name="billing_pending_credits_granted_by_fkey",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["claimed_by_user_id"],
            ["users.id"],
            name="billing_pending_credits_claimed_by_fkey",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="billing_pending_credits_pkey"),
        sa.CheckConstraint("amount_cents > 0", name="billing_pending_credits_amount_positive"),
    )
    # Index for efficient lookup of unclaimed credits by email
    op.create_index(
        "idx_billing_pending_credits_email_unclaimed",
        "billing_pending_credits",
        ["email"],
        postgresql_where=sa.text("claimed_by_user_id IS NULL"),
    )


def downgrade() -> None:
    """Drop billing_pending_credits table."""
    op.drop_index(
        "idx_billing_pending_credits_email_unclaimed", table_name="billing_pending_credits"
    )
    op.drop_table("billing_pending_credits")
