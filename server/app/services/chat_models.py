"""
Shared models and data structures for chat streaming functionality.

This module contains the common data structures used by all LLM services
for streaming chat responses, tool calling, and status updates.
"""

from enum import Enum
from typing import Any, List, Literal, NamedTuple

from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall


class ChatStatus(Enum):
    """Status enum for chat operations."""

    ANALYZING_REQUEST = "analyzing_request"
    EXECUTING_TOOLS = "executing_tools"
    GETTING_IDEA = "getting_idea"
    UPDATING_IDEA = "updating_idea"
    GENERATING_RESPONSE = "generating_response"
    DONE = "done"


class StreamStatusEvent(NamedTuple):
    """Status update event for streaming chat."""

    type: Literal["status"]
    data: str  # ChatStatus enum value


class StreamContentEvent(NamedTuple):
    """Content chunk event for streaming chat."""

    type: Literal["content"]
    data: str


class StreamIdeaUpdateEvent(NamedTuple):
    """Idea update event for streaming chat."""

    type: Literal["idea_updated"]
    data: str


class StreamErrorEvent(NamedTuple):
    """Error event for streaming chat."""

    type: Literal["error"]
    data: str


class StreamDoneData(NamedTuple):
    """Data payload for done event."""

    idea_updated: bool
    assistant_response: str


class StreamDoneEvent(NamedTuple):
    """Completion event for streaming chat."""

    type: Literal["done"]
    data: StreamDoneData


class StreamConversationLockedEvent(NamedTuple):
    """Conversation locked event for streaming chat."""

    type: Literal["conversation_locked"]
    data: str  # Linear project URL


class ToolCallResult(NamedTuple):
    """Result from tool call processing."""

    idea_updated: bool
    tool_results: List[Any]


class StreamingResult(NamedTuple):
    """Result from streaming response collection."""

    collected_content: str
    valid_tool_calls: List[ChoiceDeltaToolCall]
