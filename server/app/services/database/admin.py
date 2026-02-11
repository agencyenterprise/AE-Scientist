"""
Database helpers for admin operations.

Provides admin-specific database operations for user credit management.
"""

import logging
from datetime import datetime
from typing import Any, List, NamedTuple, Optional

from psycopg import AsyncCursor
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class UserWithBalance(NamedTuple):
    """User data with wallet balance."""

    id: int
    email: str
    name: str
    is_active: bool
    balance_cents: int
    created_at: datetime


class PendingCredit(NamedTuple):
    """Pending credit record."""

    id: int
    email: str
    amount_cents: int
    description: Optional[str]
    granted_by_user_id: int
    granted_by_email: str
    claimed_by_user_id: Optional[int]
    claimed_at: Optional[datetime]
    created_at: datetime


class AdminDatabaseMixin(ConnectionProvider):  # pylint: disable=abstract-method
    """Mixin providing admin-specific database operations."""

    async def list_active_users_with_balances(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> tuple[List[UserWithBalance], int]:
        """List all active users with their wallet balances.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            search: Optional search term for email or name

        Returns:
            Tuple of (users, total_count)
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                # Build WHERE clause
                where_clause = "WHERE u.is_active = TRUE"
                params: List[Any] = []

                if search:
                    where_clause += " AND (u.email ILIKE %s OR u.name ILIKE %s)"
                    search_pattern = f"%{search}%"
                    params.extend([search_pattern, search_pattern])

                # Get total count
                await cursor.execute(
                    f"""
                    SELECT COUNT(*) as count
                    FROM users u
                    {where_clause}
                    """,
                    params,
                )
                count_row = await cursor.fetchone()
                total_count = count_row["count"] if count_row else 0

                # Get users with balances
                await cursor.execute(
                    f"""
                    SELECT
                        u.id,
                        u.email,
                        u.name,
                        u.is_active,
                        COALESCE(w.balance, 0) as balance_cents,
                        u.created_at
                    FROM users u
                    LEFT JOIN billing_user_wallets w ON u.id = w.user_id
                    {where_clause}
                    ORDER BY u.name ASC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, limit, offset],
                )
                rows = await cursor.fetchall() or []

        return [UserWithBalance(**row) for row in rows], total_count

    async def admin_add_credit_to_user(
        self,
        *,
        user_id: int,
        amount_cents: int,
        description: str,
        granted_by_user_id: int,
    ) -> None:
        """Add credit to a user's wallet (admin action).

        Args:
            user_id: User to add credit to
            amount_cents: Amount in cents (must be positive)
            description: Description of the credit adjustment
            granted_by_user_id: Admin user who granted the credit
        """
        if amount_cents <= 0:
            raise ValueError("Amount must be positive")

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                # Insert transaction
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
                    VALUES (%s, %s, 'adjustment', 'completed', %s, %s)
                    """,
                    (
                        user_id,
                        amount_cents,
                        description,
                        Jsonb({"granted_by_user_id": granted_by_user_id, "admin_action": True}),
                    ),
                )

                # Create wallet if doesn't exist and update balance
                await cursor.execute(
                    """
                    INSERT INTO billing_user_wallets (user_id, balance)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET balance = billing_user_wallets.balance + %s,
                        updated_at = NOW()
                    """,
                    (user_id, amount_cents, amount_cents),
                )

    async def create_pending_credit(
        self,
        *,
        email: str,
        amount_cents: int,
        description: Optional[str],
        granted_by_user_id: int,
    ) -> PendingCredit:
        """Create a pending credit for an email that hasn't registered yet.

        Args:
            email: Email address to grant credit to
            amount_cents: Amount in cents (must be positive)
            description: Optional description
            granted_by_user_id: Admin user who granted the credit

        Returns:
            The created pending credit record
        """
        if amount_cents <= 0:
            raise ValueError("Amount must be positive")

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO billing_pending_credits (
                        email,
                        amount_cents,
                        description,
                        granted_by_user_id
                    )
                    VALUES (LOWER(%s), %s, %s, %s)
                    RETURNING
                        id,
                        email,
                        amount_cents,
                        description,
                        granted_by_user_id,
                        (SELECT email FROM users WHERE id = %s) as granted_by_email,
                        claimed_by_user_id,
                        claimed_at,
                        created_at
                    """,
                    (email, amount_cents, description, granted_by_user_id, granted_by_user_id),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise RuntimeError("Failed to create pending credit")

        return PendingCredit(**row)

    async def list_pending_credits(
        self,
        *,
        include_claimed: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[PendingCredit], int]:
        """List pending credits.

        Args:
            include_claimed: Whether to include already claimed credits
            limit: Maximum results
            offset: Results to skip

        Returns:
            Tuple of (pending_credits, total_count)
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                where_clause = "" if include_claimed else "WHERE pc.claimed_by_user_id IS NULL"

                await cursor.execute(
                    f"""
                    SELECT COUNT(*) as count
                    FROM billing_pending_credits pc
                    {where_clause}
                    """,
                )
                count_row = await cursor.fetchone()
                total_count = count_row["count"] if count_row else 0

                await cursor.execute(
                    f"""
                    SELECT
                        pc.id,
                        pc.email,
                        pc.amount_cents,
                        pc.description,
                        pc.granted_by_user_id,
                        u.email as granted_by_email,
                        pc.claimed_by_user_id,
                        pc.claimed_at,
                        pc.created_at
                    FROM billing_pending_credits pc
                    JOIN users u ON pc.granted_by_user_id = u.id
                    {where_clause}
                    ORDER BY pc.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = await cursor.fetchall() or []

        return [PendingCredit(**row) for row in rows], total_count

    async def claim_pending_credits_for_user_with_cursor(
        self,
        *,
        cursor: AsyncCursor[Any],
        user_id: int,
        email: str,
    ) -> int:
        """Claim all pending credits for a newly registered user.

        Called during user registration to apply any pre-granted credits.
        This version uses an existing cursor for transaction safety.

        Args:
            cursor: Database cursor from an existing transaction
            user_id: The newly registered user's ID
            email: The user's email address

        Returns:
            Total amount in cents that was claimed
        """
        # Find and claim all pending credits for this email
        await cursor.execute(
            """
            UPDATE billing_pending_credits
            SET claimed_by_user_id = %s,
                claimed_at = NOW()
            WHERE LOWER(email) = LOWER(%s)
              AND claimed_by_user_id IS NULL
            RETURNING id, amount_cents, description
            """,
            (user_id, email),
        )
        claimed = await cursor.fetchall() or []

        if not claimed:
            return 0

        total_amount: int = sum(int(row["amount_cents"]) for row in claimed)

        # Add credits to user's wallet via transactions
        for row in claimed:
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
                VALUES (%s, %s, 'adjustment', 'completed', %s, %s)
                """,
                (
                    user_id,
                    row["amount_cents"],
                    row["description"] or "Pending credit claimed on registration",
                    Jsonb({"pending_credit_id": row["id"]}),
                ),
            )

        # Update wallet balance (wallet should already exist from registration)
        await cursor.execute(
            """
            UPDATE billing_user_wallets
            SET balance = balance + %s,
                updated_at = NOW()
            WHERE user_id = %s
            """,
            (total_amount, user_id),
        )

        return total_amount

    async def claim_pending_credits_for_user(
        self,
        *,
        user_id: int,
        email: str,
    ) -> int:
        """Claim all pending credits for a newly registered user.

        Standalone version that creates its own connection.

        Args:
            user_id: The newly registered user's ID
            email: The user's email address

        Returns:
            Total amount in cents that was claimed
        """
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                return await self.claim_pending_credits_for_user_with_cursor(
                    cursor=cursor,
                    user_id=user_id,
                    email=email,
                )
