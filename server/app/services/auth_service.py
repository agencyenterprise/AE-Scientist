"""
Authentication service.

Handles user authentication, session management, and service key validation.
"""

import logging
from typing import Optional

from app.config import settings
from app.services.clerk_service import ClerkService
from app.services.database import get_database
from app.services.database.users import UserData

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication operations."""

    def __init__(self) -> None:
        """Initialize the authentication service."""
        self.db = get_database()
        self.clerk = ClerkService()

    async def authenticate_with_clerk(self, session_token: str) -> Optional[dict]:
        """
        Authenticate user with Clerk session token.

        Supports migration from Google OAuth by linking existing users by email.

        Args:
            session_token: Clerk session token

        Returns:
            Dict with user and session_token if successful, None otherwise
        """
        try:
            # Verify Clerk session and get user info
            user_info = self.clerk.verify_session_token(session_token)
            if not user_info:
                logger.warning("Failed to verify Clerk session")
                return None

            # Check if user already exists by Clerk ID (new Clerk users)
            user = await self.db.get_user_by_clerk_id(user_info["clerk_user_id"])

            if user:
                # User already has Clerk ID - just update their info
                logger.info(f"Found existing Clerk user: {user.email}")
                updated_user = await self.db.update_user(
                    user_id=user.id, email=user_info["email"], name=user_info["name"]
                )
                if not updated_user:
                    logger.error("Failed to update existing user")
                    return None
                user = updated_user
            else:
                # Check if user exists by email (migration from Google OAuth)
                user = await self.db.get_user_by_email(user_info["email"])

                if user:
                    # Existing user from Google OAuth - link Clerk ID to their account
                    logger.info(f"Migrating existing user to Clerk: {user.email}")
                    updated_user = await self.db.update_user(
                        user_id=user.id,
                        email=user_info["email"],
                        name=user_info["name"],
                        clerk_user_id=user_info["clerk_user_id"],
                    )
                    if not updated_user:
                        logger.error("Failed to link Clerk ID to existing user")
                        return None
                    user = updated_user
                else:
                    # Brand new user - create account
                    logger.info(f"Creating new Clerk user: {user_info['email']}")
                    user = await self.db.create_user(
                        clerk_user_id=user_info["clerk_user_id"],
                        email=user_info["email"],
                        name=user_info["name"],
                    )
                    if not user:
                        logger.error("Failed to create new user")
                        return None

            # Create our internal session (for backward compatibility)
            internal_session_token = await self.db.create_user_session(
                user_id=user.id, expires_in_hours=settings.SESSION_EXPIRE_HOURS
            )
            if not internal_session_token:
                logger.error("Failed to create user session")
                return None

            logger.info(f"Successfully authenticated Clerk user: {user.email}")
            return {"user": user, "session_token": internal_session_token}

        except Exception as e:
            logger.exception(f"Error authenticating with Clerk: {e}")
            return None

    async def get_user_by_session(self, session_token: str) -> Optional[UserData]:
        """
        Get user by session token.

        Args:
            session_token: Session token

        Returns:
            UserData if valid session, None otherwise
        """
        try:
            user = await self.db.get_user_by_session_token(session_token)
            return user
        except Exception as e:
            logger.exception(f"Error getting user by session: {e}")
            return None

    async def logout_user(self, session_token: str) -> bool:
        """
        Log out user by invalidating session.

        Args:
            session_token: Session token to invalidate

        Returns:
            True if successful, False otherwise
        """
        try:
            success = await self.db.delete_user_session(session_token)
            if success:
                logger.info("User logged out successfully")
            return success
        except Exception as e:
            logger.exception(f"Error logging out user: {e}")
            return False

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        try:
            count = await self.db.delete_expired_sessions()
            if count > 0:
                logger.info(f"Cleaned up {count} expired sessions")
            return count
        except Exception as e:
            logger.exception(f"Error cleaning up expired sessions: {e}")
            return 0
