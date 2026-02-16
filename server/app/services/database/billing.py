"""
Database helpers for billing, wallets, and Stripe checkout metadata.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional

from psycopg import AsyncCursor
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import settings

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class BillingWallet(NamedTuple):
    user_id: int
    balance: int
    updated_at: datetime


class CreditTransaction(NamedTuple):
    id: int
    user_id: int
    amount: int
    transaction_type: str
    status: str
    description: Optional[str]
    metadata: Dict[str, object]
    stripe_session_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class StripeCheckoutSession(NamedTuple):
    id: int
    user_id: int
    stripe_session_id: str
    price_id: str
    status: str
    amount_added_cents: int  # Amount added to wallet (now equals Stripe amount)
    amount_cents: int  # Stripe amount paid
    currency: str
    metadata: Dict[str, object]
    created_at: datetime
    updated_at: datetime


class BillingDatabaseMixin(ConnectionProvider):  # pylint: disable=abstract-method
    """Mixin providing billing-specific persistence helpers."""

    async def ensure_user_wallet_with_cursor(
        self, *, cursor: AsyncCursor[Any], user_id: int, receives_free_balance: bool
    ) -> None:
        """Create a wallet row for the user if one does not yet exist.

        Balance is in cents:
        - Internal users (AE Studio/whitelisted): 50,000 cents ($500.00)
        - Regular users: CREDIT_CENTS_NEW_USERS (default 0)
        """
        balance = 50_000 if receives_free_balance else settings.credit_cents_new_users
        await cursor.execute(
            """
            INSERT INTO billing_user_wallets (user_id, balance)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, balance),
        )

    async def ensure_user_wallet(self, user_id: int, receives_free_balance: bool) -> None:
        """Create a wallet row for the user if one does not yet exist."""
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await self.ensure_user_wallet_with_cursor(
                    cursor=cursor,
                    user_id=user_id,
                    receives_free_balance=receives_free_balance,
                )

    async def get_user_wallet(self, user_id: int) -> Optional[BillingWallet]:
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT user_id, balance, updated_at
                    FROM billing_user_wallets
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = await cursor.fetchone()
        return BillingWallet(**row) if row else None

    async def get_user_wallet_balance(self, user_id: int) -> int:
        wallet = await self.get_user_wallet(user_id)
        if wallet is None:
            return 0
        return wallet.balance

    async def list_credit_transactions(
        self,
        user_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
        transaction_types: Optional[List[str]] = None,
    ) -> tuple[List[CreditTransaction], int]:
        """List credit transactions for a user with pagination.

        Args:
            user_id: The user's ID.
            limit: Maximum number of transactions to return.
            offset: Number of transactions to skip.
            transaction_types: List of transaction types to include.
                If None, returns all transaction types.

        Returns:
            Tuple of (transactions, total_count)
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                if transaction_types:
                    # Filter by specified transaction types
                    await cursor.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM billing_credit_transactions
                        WHERE user_id = %s AND transaction_type = ANY(%s)
                        """,
                        (user_id, transaction_types),
                    )
                    count_row = await cursor.fetchone()
                    total_count = count_row["count"] if count_row else 0

                    await cursor.execute(
                        """
                        SELECT
                            id,
                            user_id,
                            amount,
                            transaction_type,
                            status,
                            description,
                            metadata,
                            stripe_session_id,
                            created_at,
                            updated_at
                        FROM billing_credit_transactions
                        WHERE user_id = %s AND transaction_type = ANY(%s)
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (user_id, transaction_types, limit, offset),
                    )
                else:
                    # No filter - return all transaction types
                    await cursor.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM billing_credit_transactions
                        WHERE user_id = %s
                        """,
                        (user_id,),
                    )
                    count_row = await cursor.fetchone()
                    total_count = count_row["count"] if count_row else 0

                    await cursor.execute(
                        """
                        SELECT
                            id,
                            user_id,
                            amount,
                            transaction_type,
                            status,
                            description,
                            metadata,
                            stripe_session_id,
                            created_at,
                            updated_at
                        FROM billing_credit_transactions
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (user_id, limit, offset),
                    )
                rows = await cursor.fetchall() or []
        return [CreditTransaction(**row) for row in rows], total_count

    async def add_completed_transaction(
        self,
        *,
        user_id: int,
        amount: int,
        transaction_type: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
        stripe_session_id: Optional[str] = None,
    ) -> CreditTransaction:
        """Insert a completed transaction and atomically update the wallet balance."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO billing_credit_transactions (
                        user_id,
                        amount,
                        transaction_type,
                        status,
                        description,
                        metadata,
                        stripe_session_id
                    )
                    VALUES (%s, %s, %s, 'completed', %s, %s, %s)
                    RETURNING
                        id,
                        user_id,
                        amount,
                        transaction_type,
                        status,
                        description,
                        metadata,
                        stripe_session_id,
                        created_at,
                        updated_at
                    """,
                    (
                        user_id,
                        amount,
                        transaction_type,
                        description,
                        Jsonb(metadata or {}),
                        stripe_session_id,
                    ),
                )
                transaction_row = await cursor.fetchone()
                if transaction_row is None:
                    raise RuntimeError(f"Failed to insert credit transaction for user {user_id}")

                # Create wallet with 0 balance if it doesn't exist.
                # The UPDATE below will add the amount, avoiding double-credit.
                await cursor.execute(
                    """
                    INSERT INTO billing_user_wallets (user_id, balance)
                    VALUES (%s, 0)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id,),
                )
                await cursor.execute(
                    """
                    UPDATE billing_user_wallets
                    SET balance = balance + %s, updated_at = NOW()
                    WHERE user_id = %s
                    RETURNING user_id, balance, updated_at
                    """,
                    (amount, user_id),
                )
                wallet_row = await cursor.fetchone()
                if wallet_row is None:
                    raise RuntimeError(f"Failed to update wallet balance for user {user_id}")

        return CreditTransaction(**transaction_row)

    async def create_stripe_checkout_session_record(
        self,
        *,
        user_id: int,
        stripe_session_id: str,
        price_id: str,
        amount_added_cents: int,
        amount_cents: int,
        currency: str,
        metadata: Optional[Dict[str, object]] = None,
    ) -> StripeCheckoutSession:
        """Create a record of a Stripe checkout session.

        Args:
            amount_added_cents: Amount to add to wallet (in cents) - equals Stripe amount for 1:1 mapping
            amount_cents: Amount paid via Stripe (in cents)
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO billing_stripe_checkout_sessions (
                        user_id,
                        stripe_session_id,
                        price_id,
                        status,
                        amount_added_cents,
                        amount_cents,
                        currency,
                        metadata
                    )
                    VALUES (%s, %s, %s, 'created', %s, %s, %s, %s)
                    RETURNING
                        id,
                        user_id,
                        stripe_session_id,
                        price_id,
                        status,
                        amount_added_cents,
                        amount_cents,
                        currency,
                        metadata,
                        created_at,
                        updated_at
                    """,
                    (
                        user_id,
                        stripe_session_id,
                        price_id,
                        amount_added_cents,
                        amount_cents,
                        currency,
                        Jsonb(metadata or {}),
                    ),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        f"Failed to persist Stripe checkout session for user {user_id}"
                    )
        return StripeCheckoutSession(**row)

    async def update_stripe_checkout_session_status(
        self,
        stripe_session_id: str,
        status: str,
        *,
        expected_status: Optional[str] = None,
    ) -> Optional[StripeCheckoutSession]:
        """Update a Stripe checkout session status.

        Args:
            stripe_session_id: The Stripe session ID.
            status: The new status to set.
            expected_status: If provided, only update if current status matches.
                This provides atomic idempotency protection against race conditions.

        Returns:
            The updated session, or None if not found or status didn't match.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                if expected_status is not None:
                    # Atomic update: only update if current status matches expected
                    await cursor.execute(
                        """
                        UPDATE billing_stripe_checkout_sessions
                        SET status = %s, updated_at = NOW()
                        WHERE stripe_session_id = %s AND status = %s
                        RETURNING
                            id,
                            user_id,
                            stripe_session_id,
                            price_id,
                            status,
                            amount_added_cents,
                            amount_cents,
                            currency,
                            metadata,
                            created_at,
                            updated_at
                        """,
                        (status, stripe_session_id, expected_status),
                    )
                else:
                    await cursor.execute(
                        """
                        UPDATE billing_stripe_checkout_sessions
                        SET status = %s, updated_at = NOW()
                        WHERE stripe_session_id = %s
                        RETURNING
                            id,
                            user_id,
                            stripe_session_id,
                            price_id,
                            status,
                            amount_added_cents,
                            amount_cents,
                            currency,
                            metadata,
                            created_at,
                            updated_at
                        """,
                        (status, stripe_session_id),
                    )
                row = await cursor.fetchone()
        return StripeCheckoutSession(**row) if row else None

    async def get_stripe_checkout_session(
        self, stripe_session_id: str
    ) -> Optional[StripeCheckoutSession]:
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        stripe_session_id,
                        price_id,
                        status,
                        amount_added_cents,
                        amount_cents,
                        currency,
                        metadata,
                        created_at,
                        updated_at
                    FROM billing_stripe_checkout_sessions
                    WHERE stripe_session_id = %s
                    """,
                    (stripe_session_id,),
                )
                row = await cursor.fetchone()
        return StripeCheckoutSession(**row) if row else None

    async def reverse_hold_transactions(self, run_id: str) -> int:
        """Reverse all 'hold' transactions for a research run.

        Creates offsetting 'hold_reversal' transactions and updates the wallet balance.

        Args:
            run_id: The research run ID to reverse holds for.

        Returns:
            Total amount (in cents) that was reversed (positive number).
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                # Find all hold transactions for this run that haven't been reversed
                await cursor.execute(
                    """
                    SELECT id, user_id, amount, description
                    FROM billing_credit_transactions
                    WHERE transaction_type = 'hold'
                      AND metadata->>'run_id' = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM billing_credit_transactions r
                          WHERE r.transaction_type = 'hold_reversal'
                            AND r.metadata->>'reversed_transaction_id' = billing_credit_transactions.id::text
                      )
                    """,
                    (run_id,),
                )
                holds = await cursor.fetchall() or []

                if not holds:
                    return 0

                total_reversed = 0
                for hold in holds:
                    # Create reversal transaction (positive amount to offset the negative hold)
                    reversal_amount = -hold["amount"]  # Negate to reverse
                    total_reversed += reversal_amount

                    await cursor.execute(
                        """
                        INSERT INTO billing_credit_transactions (
                            user_id,
                            amount,
                            transaction_type,
                            status,
                            description,
                            metadata
                        )
                        VALUES (%s, %s, 'hold_reversal', 'completed', %s, %s)
                        """,
                        (
                            hold["user_id"],
                            reversal_amount,
                            f"Reversal of hold for run {run_id}",
                            Jsonb(
                                {
                                    "run_id": run_id,
                                    "reversed_transaction_id": str(hold["id"]),
                                }
                            ),
                        ),
                    )

                    # Update wallet balance
                    await cursor.execute(
                        """
                        UPDATE billing_user_wallets
                        SET balance = balance + %s, updated_at = NOW()
                        WHERE user_id = %s
                        """,
                        (reversal_amount, hold["user_id"]),
                    )

                return total_reversed

    async def get_refund_for_run(self, run_id: str) -> int | None:
        """Get refund amount (in cents) for a failed run, if any.

        Args:
            run_id: The research run ID to check for refunds.

        Returns:
            The refund amount in cents if a refund exists, None otherwise.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT amount FROM billing_credit_transactions
                    WHERE transaction_type = 'adjustment'
                      AND metadata->>'action' = 'failed_run_refund'
                      AND metadata->>'run_id' = %s
                    LIMIT 1
                    """,
                    (run_id,),
                )
                row = await cursor.fetchone()
        return row["amount"] if row else None

    async def get_unreversed_hold_total_for_run(self, run_id: str) -> int:
        """Get the total unreversed hold amount (in cents) for a research run.

        Args:
            run_id: The research run ID.

        Returns:
            Total hold amount in cents (positive number). Returns 0 if no holds exist.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT COALESCE(SUM(ABS(amount)), 0) as total
                    FROM billing_credit_transactions
                    WHERE transaction_type = 'hold'
                      AND metadata->>'run_id' = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM billing_credit_transactions r
                          WHERE r.transaction_type = 'hold_reversal'
                            AND r.metadata->>'reversed_transaction_id' = billing_credit_transactions.id::text
                      )
                    """,
                    (run_id,),
                )
                row = await cursor.fetchone()
        return int(row["total"]) if row else 0

    async def get_transaction_by_stripe_refund_id(
        self, refund_id: str
    ) -> Optional[CreditTransaction]:
        """Look up a transaction by Stripe refund ID for idempotency checking.

        Args:
            refund_id: The Stripe refund ID (e.g., 're_xxx').

        Returns:
            The transaction if found, None otherwise.
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        amount,
                        transaction_type,
                        status,
                        description,
                        metadata,
                        stripe_session_id,
                        created_at,
                        updated_at
                    FROM billing_credit_transactions
                    WHERE transaction_type = 'refund'
                      AND metadata->>'refund_id' = %s
                    LIMIT 1
                    """,
                    (refund_id,),
                )
                row = await cursor.fetchone()
        return CreditTransaction(**row) if row else None
