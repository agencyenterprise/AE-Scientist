from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from multiprocessing.managers import DictProxy
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from .journal import Node


RegistryStatus = Literal["running", "terminated", "completed"]
logger = logging.getLogger(__name__)


@dataclass
class ExecutionEntry:
    node_id: str
    node: Optional["Node"]
    status: RegistryStatus = "running"
    payload: Optional[str] = None


_shared_pid_state: DictProxy | None = None
_entries: dict[str, ExecutionEntry] = {}
_lock = threading.RLock()


def setup_shared_pid_state(shared_state: DictProxy) -> None:
    """Configure the shared PID dictionary used across processes."""
    global _shared_pid_state
    _shared_pid_state = shared_state
    logger.info("Execution registry shared state configured (id=%s)", id(shared_state))


def get_shared_pid_state() -> DictProxy | None:
    return _shared_pid_state


def register_execution(*, execution_id: str, node: Optional["Node"]) -> None:
    """Register a new execution with the controller."""
    with _lock:
        _entries[execution_id] = ExecutionEntry(
            node_id=node.id if node is not None else execution_id,
            node=node,
            status="running",
            payload=None,
        )
    logger.info(
        "Registered execution_id=%s for node=%s (feedback_pending=%s)",
        execution_id,
        node.id if node is not None else "standalone",
        bool(node.user_feedback_pending) if node is not None else False,
    )


def update_pid(*, execution_id: str, pid: int) -> None:
    """Update the interpreter PID for a running execution."""
    shared = _shared_pid_state
    if shared is None:
        logger.warning(
            "Shared PID state not configured when updating pid for execution_id=%s", execution_id
        )
        return
    shared[execution_id] = {"pid": pid, "reported_at": time.time()}
    logger.info("Recorded pid=%s for execution_id=%s", pid, execution_id)


def clear_pid(execution_id: str) -> None:
    shared = _shared_pid_state
    if shared is None:
        return
    try:
        shared.pop(execution_id, None)
        logger.debug("Cleared pid for execution_id=%s", execution_id)
    except Exception:
        # Manager proxies can raise when shutting down; ignore best-effort cleanup.
        logger.debug("Failed to clear pid for execution_id=%s during shutdown", execution_id)
        pass


def mark_completed(execution_id: str) -> None:
    with _lock:
        entry = _entries.get(execution_id)
        if entry is not None:
            entry.status = "completed"
            logger.info("Marked execution_id=%s as completed", execution_id)
    clear_pid(execution_id)


def mark_terminated(*, execution_id: str, payload: str) -> Optional["Node"]:
    with _lock:
        entry = _entries.get(execution_id)
        if entry is None:
            return None
        entry.status = "terminated"
        entry.payload = payload
        node = entry.node
        if node is not None:
            node.is_user_feedback = True
            node.user_feedback_payload = payload
            node.user_feedback_pending = True
            logger.info(
                "Execution_id=%s terminated. Payload length=%s. Node=%s now pending user feedback.",
                execution_id,
                len(payload),
                node.id,
            )
        else:
            logger.info(
                "Execution_id=%s terminated without node reference (payload length=%s).",
                execution_id,
                len(payload),
            )
        return node


def get_entry(execution_id: str) -> Optional[ExecutionEntry]:
    with _lock:
        entry = _entries.get(execution_id)
        if entry is None:
            return None
        return ExecutionEntry(
            node_id=entry.node_id,
            node=entry.node,
            status=entry.status,
            payload=entry.payload,
        )


def get_pid(execution_id: str) -> Optional[int]:
    shared = _shared_pid_state
    if shared is None:
        logger.debug(
            "Shared PID state unavailable while reading pid for execution_id=%s", execution_id
        )
        return None
    entry = shared.get(execution_id)
    if not entry:
        logger.debug("No pid entry found for execution_id=%s", execution_id)
        return None
    pid = entry.get("pid")
    return int(pid) if pid is not None else None


def clear_execution(execution_id: str) -> None:
    with _lock:
        _entries.pop(execution_id, None)
        logger.info("Cleared execution registry entry for execution_id=%s", execution_id)
    clear_pid(execution_id)


def has_active_execution(execution_id: str) -> bool:
    with _lock:
        entry = _entries.get(execution_id)
        is_active = entry is not None and entry.status == "running"
    logger.debug("has_active_execution(%s) -> %s", execution_id, is_active)
    return is_active


def begin_termination(
    execution_id: str, payload: str
) -> tuple[str, Optional[int], Optional["Node"]]:
    """
    Prepare execution for termination.

    Returns tuple(status, pid, node) where status is one of:
        - "not_found": execution id missing
        - "conflict": execution no longer running
        - "ok": termination may proceed
    """
    with _lock:
        entry = _entries.get(execution_id)
        if entry is None:
            logger.warning("Termination requested for unknown execution_id=%s", execution_id)
            return "not_found", None, None
        if entry.status != "running":
            logger.warning(
                "Termination requested but execution already %s for execution_id=%s",
                entry.status,
                execution_id,
            )
            return "conflict", None, None
    pid = get_pid(execution_id)
    if pid is None:
        logger.warning(
            "Termination requested but PID missing for execution_id=%s; marking conflict",
            execution_id,
        )
        return "conflict", None, None
    node = mark_terminated(execution_id=execution_id, payload=payload)
    logger.info("Termination handshake ready for execution_id=%s with pid=%s", execution_id, pid)
    return "ok", pid, node


def is_terminated(execution_id: str) -> bool:
    with _lock:
        entry = _entries.get(execution_id)
        return entry is not None and entry.status == "terminated"
