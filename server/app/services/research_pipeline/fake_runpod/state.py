"""Global state for the fake RunPod server.

This module exists to avoid circular imports between server.py and runner/.
"""

import threading
from typing import TYPE_CHECKING, Dict

from .models import ExecutionRecord

if TYPE_CHECKING:
    from .runner import FakeRunner

# Speed factor - set via --speed CLI argument
_speed_factor: float = 1.0

# Global state
_lock = threading.Lock()
_executions_by_id: Dict[str, ExecutionRecord] = {}
_runners_by_run_id: Dict[str, "FakeRunner"] = {}


def set_speed_factor(factor: float) -> None:
    """Set the global speed factor for all wait times."""
    global _speed_factor
    _speed_factor = factor


def get_speed_factor() -> float:
    """Get the current speed factor."""
    return _speed_factor


def get_lock() -> threading.Lock:
    """Get the global lock for thread-safe access."""
    return _lock


def get_executions() -> Dict[str, ExecutionRecord]:
    """Get the executions dictionary."""
    return _executions_by_id


def get_runners() -> Dict[str, "FakeRunner"]:
    """Get the runners dictionary."""
    return _runners_by_run_id
