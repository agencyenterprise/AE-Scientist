"""
Clerk authentication service.

Handles Clerk JWT verification and user info retrieval.
"""

import base64
import logging
from typing import Optional

import jwt
from clerk_backend_api import Clerk
from jwt import PyJWKClient

from app.config import settings

logger = logging.getLogger(__name__)


class ClerkService:
    """Service for handling Clerk authentication."""
    jwks_url: str
    client: Clerk
    jwks_client: PyJWKClient

    def __init__(self) -> None:
        """Initialize the Clerk service."""
        if not settings.CLERK_SECRET_KEY:
            logger.warning("CLERK_SECRET_KEY not configured")
        self.client = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)

        # JWKS client for JWT verification (networkless)
        # Extract the Clerk frontend API URL from the publishable key
        # Format: pk_test_<instance>.clerk.accounts.dev or pk_live_<instance>.clerk.com
        if settings.CLERK_PUBLISHABLE_KEY:
            # Extract domain from publishable key
            # Example: pk_test_ZG9taW5hbnQtZHJhZ29uLTg4LmNsZXJrLmFjY291bnRzLmRldg==
            # The key is base64 encoded and contains the domain
            try:
                # Get the part after pk_test_ or pk_live_
                key_parts = settings.CLERK_PUBLISHABLE_KEY.split("_")
                if len(key_parts) >= 3:
                    encoded_domain = "_".join(key_parts[2:])
                    # Decode base64 to get the domain, strip any null bytes or special chars
                    domain = base64.b64decode(encoded_domain + "==").decode("utf-8").rstrip("\x00$")
                    self.jwks_url = f"https://{domain}/.well-known/jwks.json"
            except Exception as e:
                raise ValueError(f"Error parsing Clerk publishable key: {e}") from e

        if not self.jwks_url:
            raise ValueError("CLERK_PUBLISHABLE_KEY not configured")

        self.jwks_client = PyJWKClient(self.jwks_url)

    def verify_session_token(self, jwt_token: str) -> Optional[dict]:
        """
        Verify a Clerk JWT token using networkless verification.

        Args:
            jwt_token: JWT token from Clerk (from getToken())

        Returns:
            Dict with user info if valid, None otherwise
        """
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

            logger.info(f"JWT verified successfully for user: {user_id}")

            # Get full user details from Clerk API
            user = self.client.users.get(user_id=user_id)

            if not user:
                logger.warning(f"User not found in Clerk: {user_id}")
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

            user_info = {
                "clerk_user_id": user.id,
                "email": primary_email or "",
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip()
                or primary_email
                or "User",
            }

            logger.info(f"Successfully verified Clerk user: {user_info['email']}")
            return user_info

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.exception(f"Error verifying Clerk JWT: {e}")
            return None
