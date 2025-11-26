"""
Google OAuth 2.0 service.

Handles Google OAuth flow, token exchange, and user information retrieval.
"""

import logging
from typing import Optional

from google.auth.transport import requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]

from app.config import settings

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    """Service for handling Google OAuth 2.0 authentication."""

    def __init__(self) -> None:
        """Initialize the Google OAuth service."""
        # OAuth 2.0 client configuration
        self.client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            }
        }

        # OAuth scopes
        self.scopes = [
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid",
        ]

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Google OAuth authorization URL.

        Args:
            state: Optional state parameter for security

        Returns:
            Authorization URL for redirecting users to Google
        """
        try:
            flow = Flow.from_client_config(
                self.client_config, scopes=self.scopes, redirect_uri=settings.GOOGLE_REDIRECT_URI
            )

            authorization_url, _ = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                state=state,
                prompt="consent",  # Force consent to ensure we get refresh token
            )

            return str(authorization_url)

        except Exception as e:
            logger.exception(f"Error generating authorization URL: {e}")
            raise

    def exchange_code_for_tokens(
        self, authorization_code: str, state: Optional[str] = None
    ) -> Optional[dict]:
        """
        Exchange authorization code for access and ID tokens.

        Args:
            authorization_code: Authorization code from Google
            state: State parameter for verification

        Returns:
            User information dict if successful, None otherwise
        """
        try:
            flow = Flow.from_client_config(
                self.client_config,
                scopes=self.scopes,
                redirect_uri=settings.GOOGLE_REDIRECT_URI,
                state=state,
            )

            # Exchange code for tokens
            flow.fetch_token(code=authorization_code)

            # Get user info from ID token
            id_info = id_token.verify_oauth2_token(
                flow.credentials.id_token, requests.Request(), settings.GOOGLE_CLIENT_ID
            )

            # Domain validation is handled by Google OAuth configuration

            # Extract user information
            user_info = {
                "google_id": id_info["sub"],
                "email": id_info["email"],
                "name": id_info["name"],
                "picture": id_info.get("picture"),
                "verified_email": id_info.get("email_verified", False),
                "domain": id_info.get("hd"),
            }

            logger.info(f"Successfully authenticated user: {user_info['email']}")
            return dict(user_info)

        except Exception as e:
            logger.exception(f"Error exchanging authorization code: {e}")
            return None

    # def verify_id_token(self, token: str) -> Optional[dict]:
    #     """
    #     Verify a Google ID token.

    #     Args:
    #         token: Google ID token to verify

    #     Returns:
    #         Token payload if valid, None otherwise
    #     """
    #     try:
    #         id_info = id_token.verify_oauth2_token(
    #             token, requests.Request(), settings.GOOGLE_CLIENT_ID
    #         )

    #         # Domain validation is handled by Google OAuth configuration
    #         return id_info

    #     except Exception as e:
    #         logger.exception(f"Error verifying ID token: {e}")
    #         return None
