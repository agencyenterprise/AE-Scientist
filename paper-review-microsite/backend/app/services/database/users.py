"""
User and session database operations.

Provides CRUD operations for users and user sessions.
Simplified version for AE Paper Review (no billing).
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import NamedTuple, Optional

from psycopg.rows import dict_row

from app.config import settings

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class UserData(NamedTuple):
    """User data from database."""

    id: int
    clerk_user_id: Optional[str]
    email: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UsersDatabaseMixin(ConnectionProvider):
    """Mixin for user and session database operations."""

    async def create_user(
        self,
        email: str,
        name: str,
        clerk_user_id: Optional[str] = None,
    ) -> Optional[UserData]:
        """
        Create a new user.

        Args:
            email: User email address
            name: User display name
            clerk_user_id: Clerk user ID (required for Clerk auth)

        Returns:
            User data if successful, None otherwise
        """
        try:
            insert_sql = (
                """
                INSERT INTO users (clerk_user_id, email, name)
                VALUES (%s, %s, %s)
                ON CONFLICT (clerk_user_id) DO UPDATE
                SET email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    updated_at = NOW()
                RETURNING id, clerk_user_id, email, name, is_active, created_at, updated_at
                """
                if clerk_user_id is not None
                else """
                INSERT INTO users (clerk_user_id, email, name)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE
                SET name = EXCLUDED.name,
                    clerk_user_id = COALESCE(users.clerk_user_id, EXCLUDED.clerk_user_id),
                    updated_at = NOW()
                RETURNING id, clerk_user_id, email, name, is_active, created_at, updated_at
                """
            )
            async with self.aget_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cursor:
                    await cursor.execute(
                        insert_sql,
                        (clerk_user_id, email, name),
                    )
                    result = await cursor.fetchone()
                    if result:
                        return UserData(**result)
                    return None
        except Exception as e:
            logger.exception(f"Error creating user: {e}")
            return None

    async def get_user_by_clerk_id(self, clerk_user_id: str) -> Optional[UserData]:
        """
        Get user by Clerk user ID.

        Args:
            clerk_user_id: Clerk user ID

        Returns:
            User data if found, None otherwise
        """
        try:
            async with self.aget_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cursor:
                    await cursor.execute(
                        """
                        SELECT id, clerk_user_id, email, name, is_active, created_at, updated_at
                        FROM users
                        WHERE clerk_user_id = %s AND is_active = TRUE
                        """,
                        (clerk_user_id,),
                    )
                    result = await cursor.fetchone()
                    return UserData(**result) if result else None
        except Exception as e:
            logger.exception(f"Error getting user by Clerk ID: {e}")
            return None

    async def get_user_by_email(self, email: str) -> Optional[UserData]:
        """
        Get user by email address.

        Args:
            email: User email address

        Returns:
            User data if found, None otherwise
        """
        try:
            async with self.aget_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cursor:
                    await cursor.execute(
                        """
                        SELECT id, clerk_user_id, email, name, is_active, created_at, updated_at
                        FROM users
                        WHERE email = %s AND is_active = TRUE
                        """,
                        (email,),
                    )
                    result = await cursor.fetchone()
                    return UserData(**result) if result else None
        except Exception as e:
            logger.exception(f"Error getting user by email: {e}")
            return None

    async def get_user_by_id(self, user_id: int) -> Optional[UserData]:
        """
        Get user by database ID.

        Args:
            user_id: User's primary key

        Returns:
            User data if found, None otherwise
        """
        try:
            async with self.aget_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cursor:
                    await cursor.execute(
                        """
                        SELECT id, clerk_user_id, email, name, is_active, created_at, updated_at
                        FROM users
                        WHERE id = %s
                        """,
                        (user_id,),
                    )
                    result = await cursor.fetchone()
                    return UserData(**result) if result else None
        except Exception as e:
            logger.exception("Error getting user by id %s: %s", user_id, e)
            return None

    async def update_user(
        self,
        user_id: int,
        email: str,
        name: str,
        clerk_user_id: Optional[str] = None,
    ) -> Optional[UserData]:
        """
        Update user information.

        Args:
            user_id: Database user ID
            email: Updated email address
            name: Updated display name
            clerk_user_id: Optional Clerk user ID

        Returns:
            Updated user data if successful, None otherwise
        """
        try:
            async with self.aget_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cursor:
                    await cursor.execute(
                        """
                        UPDATE users
                        SET email = %s, name = %s, clerk_user_id = %s, updated_at = NOW()
                        WHERE id = %s AND is_active = TRUE
                        RETURNING id, clerk_user_id, email, name, is_active, created_at, updated_at
                        """,
                        (email, name, clerk_user_id, user_id),
                    )
                    result = await cursor.fetchone()
                    return UserData(**result) if result else None
        except Exception as e:
            logger.exception(f"Error updating user: {e}")
            return None

    async def create_user_session(
        self, user_id: int, expires_in_hours: Optional[int] = None
    ) -> Optional[str]:
        """
        Create a new user session.

        Args:
            user_id: Database user ID
            expires_in_hours: Session duration in hours (defaults to settings)

        Returns:
            Session token if successful, None otherwise
        """
        try:
            session_token = secrets.token_urlsafe(32)
            hours = expires_in_hours or settings.session_expire_hours
            expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)

            async with self.aget_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO user_sessions (user_id, session_token, expires_at)
                        VALUES (%s, %s, %s)
                        """,
                        (user_id, session_token, expires_at),
                    )
                    return session_token
        except Exception as e:
            logger.exception(f"Error creating user session: {e}")
            return None

    async def get_user_by_session_token(self, session_token: str) -> Optional[UserData]:
        """
        Get user by session token.

        Args:
            session_token: Session token

        Returns:
            User data if valid session found, None otherwise
        """
        try:
            async with self.aget_connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cursor:
                    await cursor.execute(
                        """
                        SELECT u.id, u.clerk_user_id, u.email, u.name, u.is_active,
                               u.created_at, u.updated_at
                        FROM users u
                        JOIN user_sessions s ON u.id = s.user_id
                        WHERE s.session_token = %s
                          AND s.expires_at > NOW()
                          AND u.is_active = TRUE
                        """,
                        (session_token,),
                    )
                    result = await cursor.fetchone()
                    return UserData(**result) if result else None
        except Exception as e:
            logger.exception(f"Error getting user by session token: {e}")
            return None

    async def delete_user_session(self, session_token: str) -> bool:
        """
        Delete a user session (logout).

        Args:
            session_token: Session token to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            async with self.aget_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM user_sessions WHERE session_token = %s", (session_token,)
                    )
                    return cursor.rowcount > 0
        except Exception as e:
            logger.exception(f"Error deleting user session: {e}")
            return False

    async def delete_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions deleted
        """
        try:
            async with self.aget_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("DELETE FROM user_sessions WHERE expires_at <= NOW()")
                    deleted_count = cursor.rowcount
                    logger.debug(f"Deleted {deleted_count} expired sessions")
                    return deleted_count
        except Exception as e:
            logger.exception(f"Error deleting expired sessions: {e}")
            return 0
