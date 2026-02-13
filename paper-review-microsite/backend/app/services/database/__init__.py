"""
Database module for AE Paper Review.

Simplified database management with only user and paper review functionality.
"""

from .base import BaseDatabaseManager
from .paper_reviews import PaperReviewsDatabaseMixin, PaperReviewStatus, TokenUsageTotal
from .users import UsersDatabaseMixin

__all__ = [
    "DatabaseManager",
    "get_database",
    "PaperReviewStatus",
    "TokenUsageTotal",
]


class DatabaseManager(
    BaseDatabaseManager,
    UsersDatabaseMixin,
    PaperReviewsDatabaseMixin,
):
    """
    Main database manager for the AE Paper Review.

    Combines user and paper review database operations.
    """

    pass


# Global instance
_database_manager: DatabaseManager | None = None


def get_database() -> DatabaseManager:
    """Get the global database manager instance."""
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
    return _database_manager
