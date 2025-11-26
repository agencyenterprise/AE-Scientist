"""
Scraper errors module.

Holds exceptions shared across scraper/parser implementations.
"""


class ChatNotFound(Exception):
    """Exception raised when a shared conversation URL returns 404 or is not found."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
