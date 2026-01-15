import logging
import os
import signal
import time

logger = logging.getLogger("ai-scientist")


def send_signal_to_process_group(*, pid: int, sig: signal.Signals) -> None:
    """
    Best-effort signal delivery to a process group.

    - Prefers os.killpg(pid, sig) so children (e.g., DataLoader workers, shell pipelines)
      are terminated together.
    - Falls back to os.kill(pid, sig) if killpg is not available or fails.
    """
    try:
        if hasattr(os, "killpg"):
            os.killpg(pid, sig)
            return
    except ProcessLookupError:
        return
    except PermissionError:
        logger.warning(
            "Permission denied sending %s to process group pid=%s; falling back to os.kill",
            sig,
            pid,
            exc_info=True,
        )
    except OSError:
        logger.warning(
            "os.killpg failed sending %s to process group pid=%s; falling back to os.kill",
            sig,
            pid,
            exc_info=True,
        )
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        return
    except PermissionError:
        logger.warning(
            "Permission denied sending %s to pid=%s",
            sig,
            pid,
            exc_info=True,
        )
    except OSError:
        logger.warning(
            "os.kill failed sending %s to pid=%s",
            sig,
            pid,
            exc_info=True,
        )


def terminate_process_group(*, pid: int, grace_seconds: float) -> None:
    """
    Best-effort terminate then kill a process group.

    This is intentionally simple: it sends SIGTERM, waits up to grace_seconds, then SIGKILL.
    Callers that need stronger guarantees should additionally poll liveness.
    """
    send_signal_to_process_group(pid=pid, sig=signal.SIGTERM)
    if grace_seconds > 0:
        try:
            time.sleep(grace_seconds)
        except Exception:
            pass
    send_signal_to_process_group(pid=pid, sig=signal.SIGKILL)
