"""
Utilities for collecting hardware statistics (disk usage) and reporting them via telemetry.
"""

import logging
import subprocess
import threading
from pathlib import Path
from typing import Optional, Sequence

from .event_persistence import WebhookClient

logger = logging.getLogger("ai-scientist.telemetry")


def _du_bytes(path: Path) -> Optional[int]:
    """
    Run du in summary mode restricted to a single filesystem. Falls back to -skx if -sbx
    is unsupported. Ignores non-fatal errors produced by du while still parsing output.
    """

    def _run(flags: list[str], multiplier: int) -> Optional[int]:
        try:
            result = subprocess.run(
                ["du", *flags, "--", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
        except (FileNotFoundError, OSError):
            logger.debug("du command unavailable while measuring %s", path)
            return None
        stdout = result.stdout.strip()
        if not stdout:
            return None
        first_line = stdout.splitlines()[0]
        token = first_line.split("\t", maxsplit=1)[0].strip()
        try:
            value = float(token)
        except ValueError:
            return None
        # du may exit with code 1 when some files cannot be read; treat as success.
        if result.returncode not in (0, 1):
            return None
        return int(value * multiplier)

    # Prefer byte-accurate output; fall back to KiB if -b unsupported.
    for flags, multiplier in ((["-sbx"], 1), (["-skx"], 1024)):
        used = _run(flags, multiplier)
        if used is not None:
            return used
    logger.debug("Failed to collect du usage for path=%s", path)
    return None


def _collect_hw_stats(paths: Sequence[str]) -> list[dict[str, int | str]]:
    stats: list[dict[str, int | str]] = []
    for raw_path in paths:
        path = Path(raw_path).resolve()
        if not path.exists():
            continue
        used_bytes = _du_bytes(path=path)
        if used_bytes is None:
            continue
        stats.append(
            {
                "partition": str(path),
                "used_bytes": int(used_bytes),
            }
        )
    return stats


class HardwareStatsReporter:
    """Background reporter that periodically pushes hardware stats via webhook."""

    def __init__(
        self,
        *,
        webhook_client: WebhookClient,
        paths: Sequence[str],
        interval_seconds: int = 600,
    ) -> None:
        self._webhook = webhook_client
        self._paths = [p for p in (path.strip() for path in paths) if p]
        self._interval = max(interval_seconds, 60)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self._paths or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="HWStatsReporter", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=self._interval + 5)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                stats = _collect_hw_stats(self._paths)
                if stats:
                    self._webhook.publish_hw_stats(partitions=stats)
            except Exception:
                logger.exception("Failed to publish hardware stats payload.")
            self._stop_event.wait(timeout=self._interval)
