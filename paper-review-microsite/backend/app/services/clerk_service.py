"""
Clerk authentication service.

Handles Clerk JWT verification and user info retrieval.
"""

import base64
import logging
from typing import NamedTuple

import jwt
from clerk_backend_api import Clerk
from jwt import PyJWKClient

from app.config import settings

logger = logging.getLogger(__name__)


class ClerkUserInfo(NamedTuple):
    """User information from Clerk verification."""

    clerk_user_id: str
    email: str
    name: str


class ClerkService:
    """Service for handling Clerk authentication."""

    jwks_url: str | None
    client: Clerk | None
    jwks_client: PyJWKClient | None
    _is_configured: bool

    def __init__(self) -> None:
        """Initialize the Clerk service."""
        self._is_configured = False
        self.jwks_url = None
        self.client = None
        self.jwks_client = None

        if not settings.clerk.secret_key:
            logger.warning("CLERK_SECRET_KEY not configured - Clerk authentication will not work")
            return

        if not settings.clerk.publishable_key:
            logger.warning(
                "CLERK_PUBLISHABLE_KEY not configured - Clerk authentication will not work"
            )
            return

        try:
            self.client = Clerk(bearer_auth=settings.clerk.secret_key)

            # JWKS client for JWT verification (networkless)
            # Extract the Clerk frontend API URL from the publishable key
            # Format: pk_test_<instance>.clerk.accounts.dev or pk_live_<instance>.clerk.com
            # Extract domain from publishable key
            # Example: pk_test_ZG9taW5hbnQtZHJhZ29uLTg4LmNsZXJrLmFjY291bnRzLmRldg==
            # The key is base64 encoded and contains the domain
            # Get the part after pk_test_ or pk_live_
            key_parts = settings.clerk.publishable_key.split("_")
            if len(key_parts) >= 3:
                encoded_domain = "_".join(key_parts[2:])
                # Decode base64 to get the domain, strip any null bytes or special chars
                domain = base64.b64decode(encoded_domain + "==").decode("utf-8").rstrip("\x00$")
                self.jwks_url = f"https://{domain}/.well-known/jwks.json"
                self.jwks_client = PyJWKClient(self.jwks_url)
                self._is_configured = True
                logger.debug("Clerk service initialized successfully")
            else:
                logger.warning("Invalid CLERK_PUBLISHABLE_KEY format")
        except Exception as e:
            logger.warning("Error initializing Clerk service: %s", e)
            self._is_configured = False

    def verify_session_token(self, jwt_token: str) -> ClerkUserInfo | None:
        """
        Verify a Clerk JWT token using networkless verification.

        Args:
            jwt_token: JWT token from Clerk (from getToken())

        Returns:
            ClerkUserInfo if valid, None otherwise
        """
        if not self._is_configured or not self.jwks_client or not self.client:
            logger.error("Clerk service is not properly configured")
            return None

        try:
            # Get the signing key from Clerk's JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(jwt_token)

            # Verify the JWT signature and decode claims
            decoded = jwt.decode(
                jwt_token,
                signing_key.key,
                algorithms=["RS256"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": False,  # Clerk doesn't always set aud
                },
            )

            # Extract user_id from JWT claims
            user_id = decoded.get("sub")  # 'sub' claim contains user_id
            if not user_id:
                logger.warning("JWT missing 'sub' claim (user_id)")
                return None

            logger.debug("JWT verified successfully for user: %s", user_id)

            # Get full user details from Clerk API
            user = self.client.users.get(user_id=user_id)

            if not user or not user.id:
                logger.warning("User not found in Clerk: %s", user_id)
                return None

            # Extract user information
            primary_email = None
            if user.email_addresses:
                for email in user.email_addresses:
                    if email.id == user.primary_email_address_id:
                        primary_email = email.email_address
                        break
                if not primary_email and user.email_addresses:
                    primary_email = user.email_addresses[0].email_address

            user_info = ClerkUserInfo(
                clerk_user_id=user.id,
                email=primary_email or "",
                name=f"{user.first_name or ''} {user.last_name or ''}".strip()
                or primary_email
                or "User",
            )

            logger.debug("Successfully verified Clerk user: %s", user_info.email)
            return user_info

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token: %s", e)
            return None
        except Exception as e:
            logger.exception("Error verifying Clerk JWT: %s", e)
            return None
