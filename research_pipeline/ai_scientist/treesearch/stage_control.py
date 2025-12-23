import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

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
        logger.info(
            "Skip request accepted for stage=%s reason=%s",
            stage_name,
            _skip_request["reason"],
        )
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
