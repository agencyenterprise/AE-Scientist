"""Global state for the fake RunPod server.

This module exists to avoid circular imports between server.py and runner/.
"""

import threading
from typing import TYPE_CHECKING, Callable, Dict, Optional

from .models import ExecutionRecord

if TYPE_CHECKING:
    from .runner import FakeRunner

# Speed factor - set via --speed CLI argument
_speed_factor: float = 1.0

# Simulate failure flag - set via --simulate-failure CLI argument
_simulate_failure: bool = False

# Global state
_lock = threading.Lock()
_executions_by_id: Dict[str, ExecutionRecord] = {}
_runners_by_run_id: Dict[str, "FakeRunner"] = {}

# Runner factory - set by runner/__init__.py to avoid circular imports
_runner_factory: Optional[Callable[[str, str, str, str], "FakeRunner"]] = None


def set_speed_factor(factor: float) -> None:
    """Set the global speed factor for all wait times."""
    global _speed_factor
    _speed_factor = factor


def get_speed_factor() -> float:
    """Get the current speed factor."""
    return _speed_factor


def set_simulate_failure(enabled: bool) -> None:
    """Set the global simulate failure flag."""
    global _simulate_failure
    _simulate_failure = enabled


def get_simulate_failure() -> bool:
    """Get the current simulate failure flag."""
    return _simulate_failure


def get_lock() -> threading.Lock:
    """Get the global lock for thread-safe access."""
    return _lock


def get_executions() -> Dict[str, ExecutionRecord]:
    """Get the executions dictionary."""
    return _executions_by_id


def get_runners() -> Dict[str, "FakeRunner"]:
    """Get the runners dictionary."""
    return _runners_by_run_id


def register_runner_factory(factory: Callable[[str, str, str, str], "FakeRunner"]) -> None:
    """Register the runner factory function.

    This is called by runner/__init__.py to register the FakeRunner constructor.
    """
    global _runner_factory
    _runner_factory = factory


def create_runner(run_id: str, pod_id: str, webhook_url: str, webhook_token: str) -> "FakeRunner":
    """Create a FakeRunner instance using the registered factory."""
    if _runner_factory is None:
        raise RuntimeError("Runner factory not registered. Import runner module first.")
    return _runner_factory(run_id, pod_id, webhook_url, webhook_token)
