from collections.abc import Callable
from typing import Dict, List

from .interpreter import ExecutionResult

# Public type aliases used across treesearch components.

# Callback invoked after executing generated code. The boolean indicates whether the
# execution is considered successful, and the result contains stdout/stderr/metadata.
ExecCallbackType = Callable[[str, bool], ExecutionResult]

# Prompt structures used to build LLM system/user messages.
PromptValue = str | List[str] | Dict[str, str | List[str]] | None
PromptType = Dict[str, PromptValue]

# Event payloads emitted to the UI/logging layer.
EventDataType = Dict[str, str | int]
