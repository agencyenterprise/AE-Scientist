"""
Authentication service.

Handles user authentication, session management, and service key validation.
"""

import logging
from typing import Optional

from app.config import settings
from app.services.database import get_database
from app.services.database.users import UserData
from app.services.google_oauth_service import GoogleOAuthService

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication operations."""

    def __init__(self) -> None:
        """Initialize the authentication service."""
        self.db = get_database()
        self.google_oauth = GoogleOAuthService()

    def authenticate_with_google(
        self, authorization_code: str, state: Optional[str] = None
    ) -> Optional[dict]:
        """
        Authenticate user with Google OAuth code.

        Args:
            authorization_code: OAuth authorization code from Google
            state: State parameter for verification

        Returns:
            Dict with user and session_token if successful, None otherwise
        """
        try:
            # Exchange code for user info
            user_info = self.google_oauth.exchange_code_for_tokens(authorization_code, state)
            if not user_info:
                logger.warning("Failed to exchange authorization code")
                return None

            # Check if user already exists
            user = self.db.get_user_by_google_id(user_info["google_id"])

            if user:
                # Update existing user info
                updated_user = self.db.update_user(
                    user_id=user.id, email=user_info["email"], name=user_info["name"]
                )
                if not updated_user:
                    logger.error("Failed to update existing user")
                    return None
                user = updated_user
            else:
                # Create new user
                user = self.db.create_user(
                    google_id=user_info["google_id"],
                    email=user_info["email"],
                    name=user_info["name"],
                )
                if not user:
                    logger.error("Failed to create new user")
                    return None

            # Create session
            session_token = self.db.create_user_session(
                user_id=user.id, expires_in_hours=settings.SESSION_EXPIRE_HOURS
            )
            if not session_token:
                logger.error("Failed to create user session")
                return None

            logger.info(f"Successfully authenticated user: {user.email}")
            return {"user": user, "session_token": session_token}

        except Exception as e:
            logger.exception(f"Error authenticating with Google: {e}")
            return None

    def get_user_by_session(self, session_token: str) -> Optional[UserData]:
        """
        Get user by session token.

        Args:
            session_token: Session token

        Returns:
            UserData if valid session, None otherwise
        """
        try:
            user = self.db.get_user_by_session_token(session_token)
            return user
        except Exception as e:
            logger.exception(f"Error getting user by session: {e}")
            return None

    def logout_user(self, session_token: str) -> bool:
        """
        Log out user by invalidating session.

        Args:
            session_token: Session token to invalidate

        Returns:
            True if successful, False otherwise
        """
        try:
            success = self.db.delete_user_session(session_token)
            if success:
                logger.info("User logged out successfully")
            return success
        except Exception as e:
            logger.exception(f"Error logging out user: {e}")
            return False

    def validate_service_key(self, api_key: str) -> Optional[dict]:
        """
        Validate service API key.

        Args:
            api_key: Service API key

        Returns:
            Service info dict if valid, None otherwise
        """
        try:
            service = self.db.validate_service_key(api_key)
            if service:
                logger.debug(f"Valid service key for: {service['service_name']}")
            return service
        except Exception as e:
            logger.exception(f"Error validating service key: {e}")
            return None

    def create_service_key(self, service_name: str) -> Optional[tuple[str, dict]]:
        """
        Create a new service API key.

        Args:
            service_name: Name of the service

        Returns:
            Tuple of (api_key, service_info) if successful, None otherwise
        """
        try:
            result = self.db.create_service_key(service_name)
            if result:
                api_key, service_info = result
                logger.info(f"Created service key for: {service_name}")
                return api_key, service_info
            return None
        except Exception as e:
            logger.exception(f"Error creating service key: {e}")
            return None

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        try:
            count = self.db.delete_expired_sessions()
            if count > 0:
                logger.info(f"Cleaned up {count} expired sessions")
            return count
        except Exception as e:
            logger.exception(f"Error cleaning up expired sessions: {e}")
            return 0

    def get_google_auth_url(self, state: Optional[str] = None) -> str:
        """
        Get Google OAuth authorization URL.

        Args:
            state: Optional state parameter

        Returns:
            Google OAuth authorization URL
        """
        return self.google_oauth.get_authorization_url(state)
