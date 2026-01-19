import logging
import signal
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from . import execution_registry
from .events import BaseEvent, RunLogEvent
from .process_utils import send_signal_to_process_group

logger = logging.getLogger(__name__)
_lock = threading.RLock()


def _default_state() -> Dict[str, Any]:
    return {
        "stage_name": None,
        "stage_number": None,
        "can_be_skipped": False,
        "cannot_skip_reason": "Stage not started",
        "skip_pending": False,
        "skip_reason": None,
        "updated_at": time.time(),
    }


_stage_state: Dict[str, Any] = _default_state()
_skip_request: Optional[Dict[str, Any]] = None
_event_callback: Optional[Callable[[BaseEvent], None]] = None


def register_event_callback(callback: Optional[Callable[[BaseEvent], None]]) -> None:
    """Register a callback for emitting run events (e.g., telemetry)."""
    global _event_callback
    _event_callback = callback


def _emit_skip_log(stage_name: str, reason: str) -> None:
    """Emit a structured run log event when a skip request is accepted."""
    if _event_callback is None:
        return
    message = f"Skip request accepted for {stage_name}: {reason}"
    try:
        _event_callback(RunLogEvent(message=message, level="info"))
    except Exception:
        logger.exception("Failed to emit skip run log event for stage %s", stage_name)


def _terminate_active_executions_for_stage(*, stage_name: str, reason: str) -> None:
    """Kill any active worker processes for the provided stage."""
    active_exec_ids = execution_registry.list_active_executions(stage_name=stage_name)
    if not active_exec_ids:
        logger.info(
            "No active executions found for stage=%s when processing skip request.", stage_name
        )
        return
    payload = reason or f"Stage {stage_name} skipped by operator."
    logger.info(
        "Terminating %s active execution(s) for stage=%s due to skip request.",
        len(active_exec_ids),
        stage_name,
    )
    for execution_id in active_exec_ids:
        status, pid, _node = execution_registry.begin_termination(
            execution_id=execution_id, payload=payload
        )
        if status != "ok" or pid is None:
            logger.warning(
                "Unable to terminate execution_id=%s for stage=%s (status=%s).",
                execution_id,
                stage_name,
                status,
            )
            execution_registry.flag_skip_pending(
                execution_id=execution_id,
                reason=payload,
            )
            continue
        try:
            send_signal_to_process_group(pid=pid, sig=signal.SIGKILL)
            logger.info(
                "Sent SIGKILL to pid=%s for execution_id=%s (stage=%s).",
                pid,
                execution_id,
                stage_name,
            )
        except ProcessLookupError:
            logger.info(
                "Process already exited before skip termination for execution_id=%s.",
                execution_id,
            )
        except PermissionError:
            logger.exception(
                "Permission error while terminating pid=%s for execution_id=%s.",
                pid,
                execution_id,
            )


def reset_stage_state() -> None:
    """Reset the shared stage skip state (called at startup and shutdown)."""
    global _stage_state, _skip_request
    with _lock:
        _stage_state = _default_state()
        _skip_request = None
        logger.info("Stage control state reset.")


def publish_stage_state(
    *,
    stage_name: str,
    stage_number: int,
    can_be_skipped: bool,
    cannot_skip_reason: Optional[str],
) -> None:
    """
    Update the currently running stage info along with whether it may be skipped.
    """
    global _stage_state, _skip_request
    with _lock:
        current_stage = _stage_state.get("stage_name")
        stage_changed = current_stage is not None and current_stage != stage_name
        if stage_changed:
            # Stage changed; discard stale skip requests.
            _skip_request = None
            _stage_state["skip_pending"] = False
            _stage_state["skip_reason"] = None
            logger.info(
                "Stage changed from %s to %s; cleared pending skip request.",
                current_stage,
                stage_name,
            )

        # Check if state actually changed before logging
        current_can_skip = _stage_state.get("can_be_skipped", False)
        current_reason = _stage_state.get("cannot_skip_reason")
        new_cannot_skip_reason = (
            None if can_be_skipped else (cannot_skip_reason or "Stage cannot be skipped yet.")
        )
        state_changed = (
            stage_changed
            or _stage_state.get("stage_number") != stage_number
            or current_can_skip != bool(can_be_skipped)
            or current_reason != new_cannot_skip_reason
        )

        _stage_state["stage_name"] = stage_name
        _stage_state["stage_number"] = stage_number
        _stage_state["can_be_skipped"] = bool(can_be_skipped)
        _stage_state["cannot_skip_reason"] = new_cannot_skip_reason
        _stage_state["updated_at"] = time.time()

        if state_changed:
            logger.info(
                "Stage state updated: stage=%s number=%s can_skip=%s reason=%s",
                stage_name,
                stage_number,
                can_be_skipped,
                new_cannot_skip_reason,
            )


def clear_stage_state() -> None:
    """Clear the stage state when no stages are running."""
    reset_stage_state()


def request_stage_skip(*, reason: Optional[str] = None) -> Tuple[bool, str]:
    """
    Request the currently running stage to be skipped.

    Returns (ok, message). When ok=False the message explains why skipping is not allowed.
    """
    global _skip_request
    with _lock:
        stage_name = _stage_state.get("stage_name")
        if stage_name is None:
            logger.info("Skip request rejected: no active stage.")
            return False, "No active stage to skip."
        if not _stage_state.get("can_be_skipped", False):
            blocking_reason = (
                _stage_state.get("cannot_skip_reason") or "Stage cannot be skipped yet."
            )
            logger.info(
                "Skip request rejected for stage=%s: %s",
                stage_name,
                blocking_reason,
            )
            return False, blocking_reason
        if _skip_request is not None and _skip_request.get("stage") == stage_name:
            logger.info(
                "Skip already pending for stage=%s; ignoring duplicate request.", stage_name
            )
            return True, f"Skip already requested for stage {stage_name}."
        _skip_request = {
            "stage": stage_name,
            "reason": reason or "Stage skip requested by operator.",
            "requested_at": time.time(),
        }
        _stage_state["skip_pending"] = True
        _stage_state["skip_reason"] = _skip_request["reason"]
        _terminate_active_executions_for_stage(
            stage_name=stage_name, reason=_skip_request["reason"]
        )
        logger.info(
            "Skip request accepted for stage=%s reason=%s",
            stage_name,
            _skip_request["reason"],
        )
        _emit_skip_log(stage_name=stage_name, reason=_skip_request["reason"])
        return True, f"Skip requested for stage {stage_name}."


def consume_skip_request(*, stage_name: str) -> Optional[str]:
    """
    Consume a pending skip request for the provided stage.

    Returns the skip reason if there was a pending request targeting the given stage.
    """
    global _skip_request
    with _lock:
        if _skip_request is None:
            return None
        if _skip_request.get("stage") != stage_name:
            return None
        reason = str(_skip_request.get("reason") or "Stage skip requested.")
        _skip_request = None
        _stage_state["skip_pending"] = False
        _stage_state["skip_reason"] = None
        logger.info("Skip request consumed for stage=%s reason=%s", stage_name, reason)
        return reason


def get_stage_state() -> Dict[str, Any]:
    """Return a snapshot of the current stage state for diagnostics or API responses."""
    with _lock:
        return dict(_stage_state)
