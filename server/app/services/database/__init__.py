"""
Database module for AE Scientist

Provides a modular database management system organized by domain.
Each domain has its own mixin class with specialized methods.
"""

from .base import BaseDatabaseManager
from .chat_messages import ChatMessagesMixin
from .chat_summaries import ChatSummariesMixin
from .conversations import ConversationsMixin
from .file_attachments import FileAttachmentsMixin
from .ideas import IdeasMixin
from .imported_conversation_summaries import ImportedConversationSummariesMixin
from .llm_defaults import LLMDefaultsMixin
from .memories import ConversationMemoriesMixin
from .prompts import PromptsMixin
from .service_keys import ServiceKeysDatabaseMixin
from .users import UsersDatabaseMixin


class DatabaseManager(
    BaseDatabaseManager,
    ConversationsMixin,
    IdeasMixin,
    ChatMessagesMixin,
    PromptsMixin,
    FileAttachmentsMixin,
    LLMDefaultsMixin,
    UsersDatabaseMixin,
    ServiceKeysDatabaseMixin,
    ImportedConversationSummariesMixin,
    ChatSummariesMixin,
    ConversationMemoriesMixin,
):
    """
    Main database manager that combines all domain-specific functionality.

    This class inherits from all the mixin classes to provide a unified
    interface for all database operations.
    """

    pass


# Global instance
_database_manager = None


def get_database() -> DatabaseManager:
    """Get the global database manager instance."""
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
    return _database_manager
