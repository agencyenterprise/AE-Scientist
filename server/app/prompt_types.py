"""
Prompt types enumeration for the AE Scientist

This module contains enums for different types of prompts used throughout the application.
"""

from enum import Enum


class PromptTypes(str, Enum):
    """Enumeration of available prompt types."""

    IDEA_CHAT = "idea_chat"
    IDEA_GENERATION = "idea_generation"
