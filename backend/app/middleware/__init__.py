"""
Middleware module for AE Scientist

This module contains all middleware components including authentication.
"""

from app.middleware.auth import AuthenticationMiddleware

__all__ = [
    "AuthenticationMiddleware",
]
