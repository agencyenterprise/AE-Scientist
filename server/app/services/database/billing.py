"""
Database helpers for billing, wallets, and Stripe checkout metadata.
"""

import logging
from datetime import datetime
from typing import Dict, List, NamedTuple, Optional

import psycopg2.extras

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
    credits: int
    amount_cents: int
    currency: str
    metadata: Dict[str, object]
    created_at: datetime
    updated_at: datetime


class BillingDatabaseMixin(ConnectionProvider):
    """Mixin providing billing-specific persistence helpers."""

    def ensure_user_wallet(self, user_id: int, is_ae_user: bool) -> None:
        """Create a wallet row for the user if one does not yet exist."""
        balance = 10_000 if is_ae_user else 10
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO billing_user_wallets (user_id, balance)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id, balance),
                )

    def get_user_wallet(self, user_id: int) -> Optional[BillingWallet]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT user_id, balance, updated_at
                    FROM billing_user_wallets
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
        return BillingWallet(**row) if row else None

    def get_user_wallet_balance(self, user_id: int) -> int:
        wallet = self.get_user_wallet(user_id)
        if wallet is None:
            return 0
        return wallet.balance

    def list_credit_transactions(
        self, user_id: int, *, limit: int = 20, offset: int = 0
    ) -> List[CreditTransaction]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
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
                rows = cursor.fetchall() or []
        return [CreditTransaction(**row) for row in rows]

    def add_completed_transaction(
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
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
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
                        psycopg2.extras.Json(metadata or {}),
                        stripe_session_id,
                    ),
                )
                transaction_row = cursor.fetchone()
                if transaction_row is None:
                    raise RuntimeError(f"Failed to insert credit transaction for user {user_id}")

                cursor.execute(
                    """
                    INSERT INTO billing_user_wallets (user_id, balance)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id, max(amount, 0)),
                )
                cursor.execute(
                    """
                    UPDATE billing_user_wallets
                    SET balance = balance + %s, updated_at = NOW()
                    WHERE user_id = %s
                    RETURNING user_id, balance, updated_at
                    """,
                    (amount, user_id),
                )
                wallet_row = cursor.fetchone()
                if wallet_row is None:
                    raise RuntimeError(f"Failed to update wallet balance for user {user_id}")

        return CreditTransaction(**transaction_row)

    def create_stripe_checkout_session_record(
        self,
        *,
        user_id: int,
        stripe_session_id: str,
        price_id: str,
        credits: int,
        amount_cents: int,
        currency: str,
        metadata: Optional[Dict[str, object]] = None,
    ) -> StripeCheckoutSession:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    INSERT INTO billing_stripe_checkout_sessions (
                        user_id,
                        stripe_session_id,
                        price_id,
                        status,
                        credits,
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
                        credits,
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
                        credits,
                        amount_cents,
                        currency,
                        psycopg2.extras.Json(metadata or {}),
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        f"Failed to persist Stripe checkout session for user {user_id}"
                    )
        return StripeCheckoutSession(**row)

    def update_stripe_checkout_session_status(
        self, stripe_session_id: str, status: str
    ) -> Optional[StripeCheckoutSession]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
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
                        credits,
                        amount_cents,
                        currency,
                        metadata,
                        created_at,
                        updated_at
                    """,
                    (status, stripe_session_id),
                )
                row = cursor.fetchone()
        return StripeCheckoutSession(**row) if row else None

    def get_stripe_checkout_session(
        self, stripe_session_id: str
    ) -> Optional[StripeCheckoutSession]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        stripe_session_id,
                        price_id,
                        status,
                        credits,
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
                row = cursor.fetchone()
        return StripeCheckoutSession(**row) if row else None
