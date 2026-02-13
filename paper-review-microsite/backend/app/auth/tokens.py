"""Helpers for working with bearer auth tokens."""

from typing import Optional


def extract_bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    """Parse a bearer token from an Authorization header."""
    if not authorization_header:
        return None

    parts = authorization_header.strip().split(" ")
    if len(parts) != 2:
        return None

    scheme, token = parts
    if scheme.lower() != "bearer":
        return None

    if not token:
        return None

    return token
