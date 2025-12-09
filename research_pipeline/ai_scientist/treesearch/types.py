from typing import Dict, List

# Public type aliases used across treesearch components.

# Prompt structures used to build LLM system/user messages.
PromptValue = str | List[str] | Dict[str, str | List[str]] | None
PromptType = Dict[str, PromptValue]

# Event payloads emitted to the UI/logging layer.
EventDataType = Dict[str, str | int]
