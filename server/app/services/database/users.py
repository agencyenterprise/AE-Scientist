"""
User and session database operations.

Provides CRUD operations for users and user sessions.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, NamedTuple, Optional

import psycopg2.extras

from .base import ConnectionProvider
from .billing import BillingDatabaseMixin

logger = logging.getLogger(__name__)


class UserData(NamedTuple):
    """User data from database."""

    id: int
    google_id: str
    email: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UsersDatabaseMixin(ConnectionProvider):
    """Mixin for user and session database operations."""

    def create_user(self, google_id: str, email: str, name: str) -> Optional[UserData]:
        """
        Create a new user.

        Args:
            google_id: Google OAuth user ID
            email: User email address
            name: User display name

        Returns:
            User data dict if successful, None otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (google_id, email, name)
                        VALUES (%s, %s, %s)
                        RETURNING id, google_id, email, name, is_active, created_at, updated_at
                        """,
                        (google_id, email, name),
                    )
                    result = cursor.fetchone()
                    conn.commit()
                    if result:
                        try:
                            if isinstance(self, BillingDatabaseMixin):
                                self.ensure_user_wallet(int(result["id"]))
                        except Exception as wallet_error:  # noqa: BLE001
                            logger.exception(
                                "Failed to initialize wallet for user %s: %s",
                                result["id"],
                                wallet_error,
                            )
                        return UserData(**result)
                    return None
        except Exception as e:
            logger.exception(f"Error creating user: {e}")
            return None

    def get_user_by_google_id(self, google_id: str) -> Optional[UserData]:
        """
        Get user by Google ID.

        Args:
            google_id: Google OAuth user ID

        Returns:
            User data dict if found, None otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT id, google_id, email, name, is_active, created_at, updated_at
                        FROM users
                        WHERE google_id = %s AND is_active = TRUE
                        """,
                        (google_id,),
                    )
                    result = cursor.fetchone()
                    return UserData(**result) if result else None
        except Exception as e:
            logger.exception(f"Error getting user by Google ID: {e}")
            return None

    def update_user(self, user_id: int, email: str, name: str) -> Optional[UserData]:
        """
        Update user information.

        Args:
            user_id: Database user ID
            email: Updated email address
            name: Updated display name

        Returns:
            Updated user data dict if successful, None otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        UPDATE users
                        SET email = %s, name = %s, updated_at = NOW()
                        WHERE id = %s AND is_active = TRUE
                        RETURNING id, google_id, email, name, is_active, created_at, updated_at
                        """,
                        (email, name, user_id),
                    )
                    result = cursor.fetchone()
                    conn.commit()
                    return UserData(**result) if result else None
        except Exception as e:
            logger.exception(f"Error updating user: {e}")
            return None

    def create_user_session(self, user_id: int, expires_in_hours: int = 24) -> Optional[str]:
        """
        Create a new user session.

        Args:
            user_id: Database user ID
            expires_in_hours: Session duration in hours

        Returns:
            Session token if successful, None otherwise
        """
        try:
            session_token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO user_sessions (user_id, session_token, expires_at)
                        VALUES (%s, %s, %s)
                        """,
                        (user_id, session_token, expires_at),
                    )
                    conn.commit()
                    return session_token
        except Exception as e:
            logger.exception(f"Error creating user session: {e}")
            return None

    def get_user_by_session_token(self, session_token: str) -> Optional[UserData]:
        """
        Get user by session token.

        Args:
            session_token: Session token

        Returns:
            User data dict if valid session found, None otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT u.id, u.google_id, u.email, u.name, u.is_active, u.created_at, u.updated_at
                        FROM users u
                        JOIN user_sessions s ON u.id = s.user_id
                        WHERE s.session_token = %s
                        AND s.expires_at > NOW()
                        AND u.is_active = TRUE
                        """,
                        (session_token,),
                    )
                    result = cursor.fetchone()
                    return UserData(**result) if result else None
        except Exception as e:
            logger.exception(f"Error getting user by session token: {e}")
            return None

    def delete_user_session(self, session_token: str) -> bool:
        """
        Delete a user session (logout).

        Args:
            session_token: Session token to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM user_sessions WHERE session_token = %s", (session_token,)
                    )
                    conn.commit()
                    return True
        except Exception as e:
            logger.exception(f"Error deleting user session: {e}")
            return False

    def delete_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions deleted
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM user_sessions WHERE expires_at <= NOW()")
                    deleted_count = cursor.rowcount
                    conn.commit()
                    logger.info(f"Deleted {deleted_count} expired sessions")
                    return deleted_count
        except Exception as e:
            logger.exception(f"Error deleting expired sessions: {e}")
            return 0

    def list_all_users(self) -> List[UserData]:
        """
        List all active users.

        Returns:
            List of all active users sorted by name
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT id, google_id, email, name, is_active, created_at, updated_at
                        FROM users
                        WHERE is_active = TRUE
                        ORDER BY name ASC
                        """
                    )
                    return [UserData(**row) for row in cursor.fetchall()]
        except Exception as e:
            logger.exception(f"Error listing users: {e}")
            return []
