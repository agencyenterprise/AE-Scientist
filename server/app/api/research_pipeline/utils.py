"""Utility functions for research pipeline."""

import hashlib
import secrets

REQUESTER_NAME_FALLBACK = "Scientist"


def generate_run_webhook_token() -> tuple[str, str]:
    """Generate a per-run webhook token and its hash.

    Returns:
        Tuple of (plain_token, token_hash)
    """
    plain_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plain_token.encode()).hexdigest()
    return plain_token, token_hash


def extract_user_first_name(*, full_name: str) -> str:
    """Return a cleaned first-name token suitable for pod naming."""
    stripped = full_name.strip()
    if not stripped:
        return REQUESTER_NAME_FALLBACK
    token = stripped.split()[0]
    alnum_only = "".join(char for char in token if char.isalnum())
    if not alnum_only:
        return REQUESTER_NAME_FALLBACK
    return f"{alnum_only[0].upper()}{alnum_only[1:]}"
