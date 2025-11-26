"""
Service API key database operations.

Provides CRUD operations for service-to-service authentication keys.
"""

import hashlib
import logging
import secrets
from typing import Optional

import psycopg2.extras
from psycopg2.extensions import connection

logger = logging.getLogger(__name__)


class ServiceKeysDatabaseMixin:
    """Mixin for service API key database operations."""

    def create_service_key(self, service_name: str) -> Optional[tuple[str, dict]]:
        """
        Create a new service API key.

        Args:
            service_name: Name of the service (e.g., 'slack-integration')

        Returns:
            Tuple of (raw_api_key, service_key_data) if successful, None otherwise
        """
        try:
            # Generate a secure API key
            raw_api_key = f"{service_name}-{secrets.token_urlsafe(32)}"
            api_key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()

            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO service_keys (service_name, api_key_hash)
                        VALUES (%s, %s)
                        RETURNING id, service_name, is_active, created_at, last_used_at
                        """,
                        (service_name, api_key_hash),
                    )
                    result = cursor.fetchone()
                    conn.commit()

                    if result:
                        return raw_api_key, dict(result)
                    return None
        except Exception as e:
            logger.exception(f"Error creating service key: {e}")
            return None

    def validate_service_key(self, api_key: str) -> Optional[dict]:
        """
        Validate a service API key and update last_used_at.

        Args:
            api_key: Raw API key to validate

        Returns:
            Service key data dict if valid, None otherwise
        """
        try:
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    # First, check if the key exists and is active
                    cursor.execute(
                        """
                        SELECT id, service_name, is_active, created_at, last_used_at
                        FROM service_keys
                        WHERE api_key_hash = %s AND is_active = TRUE
                        """,
                        (api_key_hash,),
                    )
                    result = cursor.fetchone()

                    if result:
                        # Update last_used_at timestamp
                        cursor.execute(
                            """
                            UPDATE service_keys
                            SET last_used_at = NOW()
                            WHERE id = %s
                            """,
                            (result["id"],),
                        )
                        conn.commit()
                        return dict(result)

                    return None
        except Exception as e:
            logger.exception(f"Error validating service key: {e}")
            return None

    def deactivate_service_key(self, service_name: str) -> bool:
        """
        Deactivate a service key.

        Args:
            service_name: Name of the service

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE service_keys
                        SET is_active = FALSE
                        WHERE service_name = %s
                        """,
                        (service_name,),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.exception(f"Error deactivating service key: {e}")
            return False

    def list_service_keys(self) -> list[dict]:
        """
        List all service keys (without API key hashes).

        Returns:
            List of service key data dicts
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT id, service_name, is_active, created_at, last_used_at
                        FROM service_keys
                        ORDER BY created_at DESC
                        """
                    )
                    results = cursor.fetchall()
                    return [dict(result) for result in results]
        except Exception as e:
            logger.exception(f"Error listing service keys: {e}")
            return []

    def _get_connection(self) -> connection:
        """Get database connection. Must be implemented by parent class."""
        raise NotImplementedError("Must be implemented by parent class")
