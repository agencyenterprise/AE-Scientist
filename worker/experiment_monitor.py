"""
Comprehensive experiment monitor that watches ALL files and emits events.
This is embedded in pod_worker to ensure nothing is missed.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Set


class ExperimentMonitor:
    """Monitors experiment directory and emits events for all changes."""

    def __init__(self, exp_dir: str, run_id: str, emit_callback: Callable):
        self.exp_dir = Path(exp_dir)
        self.run_id = run_id
        self.emit = emit_callback

        self.seen_files: Set[str] = set()
        self.uploaded_plots: Set[str] = set()
        self.last_metrics: Dict[str, Any] = {}
        self.log_positions: Dict[str, int] = {}

    def scan_for_updates(self) -> None:
        """Scan experiment directory for any new files or changes."""
        if not self.exp_dir.exists():
            return

        self._check_plots()
        self._check_logs()
        self._check_metrics()
        self._check_checkpoints()
        self._check_config_changes()

    def _check_plots(self) -> None:
        """Find and upload new plots."""
        plot_patterns = ["**/*.png", "**/*.jpg", "**/*.jpeg", "**/*plot*.pdf"]

        for pattern in plot_patterns:
            for plot_file in self.exp_dir.glob(pattern):
                rel_path = str(plot_file.relative_to(self.exp_dir))

                if rel_path not in self.uploaded_plots:
                    self.uploaded_plots.add(rel_path)

                    # Get file size safely - file might be moved by parallel agent
                    try:
                        size_bytes = plot_file.stat().st_size
                    except (FileNotFoundError, OSError):
                        # File was moved between glob and stat - skip for now,
                        # will catch it in new location on next scan
                        self.uploaded_plots.remove(rel_path)
                        continue

                    self.emit(
                        "ai.artifact.detected",
                        {
                            "run_id": self.run_id,
                            "path": rel_path,
                            "type": "plot",
                            "size_bytes": size_bytes,
                        },
                    )

    def _check_logs(self) -> None:
        """Stream new log lines."""
        log_files = list(self.exp_dir.glob("**/*.log")) + list(
            self.exp_dir.glob("**/logs/**/*.txt")
        )

        for log_file in log_files:
            rel_path = str(log_file.relative_to(self.exp_dir))

            if rel_path not in self.log_positions:
                self.log_positions[rel_path] = 0

            try:
                with open(log_file, "r") as f:
                    f.seek(self.log_positions[rel_path])
                    new_lines = f.readlines()

                    for line in new_lines[:50]:
                        line = line.strip()
                        if line and len(line) > 5:
                            level = self._detect_log_level(line)
                            self.emit(
                                "ai.run.log",
                                {
                                    "run_id": self.run_id,
                                    "message": line[:1000],
                                    "level": level,
                                    "source": rel_path,
                                },
                            )

                    self.log_positions[rel_path] = f.tell()
            except Exception:
                pass

    def _check_metrics(self) -> None:
        """Parse and emit metrics from experiment data files."""
        metric_files = list(self.exp_dir.glob("**/experiment_data.npy")) + list(
            self.exp_dir.glob("**/metrics.json")
        )

        for metric_file in metric_files:
            rel_path = str(metric_file.relative_to(self.exp_dir))

            try:
                if metric_file.suffix == ".npy":
                    import numpy as np

                    data = np.load(metric_file, allow_pickle=True).item()
                    self._emit_metrics_from_dict(data, rel_path)
                elif metric_file.suffix == ".json":
                    with open(metric_file) as f:
                        data = json.load(f)
                    self._emit_metrics_from_dict(data, rel_path)
            except Exception:
                pass

    def _emit_metrics_from_dict(self, data: Dict, source: str) -> None:
        """Extract and emit metrics from structured data."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    metric_key = f"{source}:{key}"
                    if (
                        metric_key not in self.last_metrics
                        or self.last_metrics[metric_key] != value
                    ):
                        self.last_metrics[metric_key] = value
                        self.emit(
                            "ai.run.stage_metric",
                            {
                                "run_id": self.run_id,
                                "stage": self._infer_stage(source),
                                "name": key,
                                "value": value,
                            },
                        )

    def _check_checkpoints(self) -> None:
        """Find model checkpoints."""
        checkpoint_files = (
            list(self.exp_dir.glob("**/*.pt"))
            + list(self.exp_dir.glob("**/*.pth"))
            + list(self.exp_dir.glob("**/*.ckpt"))
        )

        for ckpt in checkpoint_files:
            rel_path = str(ckpt.relative_to(self.exp_dir))
            if rel_path not in self.seen_files:
                self.seen_files.add(rel_path)

                # Get file size safely - file might be moved/deleted
                try:
                    size_bytes = ckpt.stat().st_size
                except (FileNotFoundError, OSError):
                    self.seen_files.remove(rel_path)
                    continue

                self.emit(
                    "ai.artifact.detected",
                    {
                        "run_id": self.run_id,
                        "path": rel_path,
                        "type": "checkpoint",
                        "size_bytes": size_bytes,
                    },
                )

    def _check_config_changes(self) -> None:
        """Monitor config file changes."""
        config_files = list(self.exp_dir.glob("**/*.yaml")) + list(self.exp_dir.glob("**/*.json"))

        for config_file in config_files:
            if "experiment_data" in config_file.name:
                continue

            rel_path = str(config_file.relative_to(self.exp_dir))
            file_hash = self._file_hash(config_file)
            hash_key = f"{rel_path}:{file_hash}"

            if hash_key not in self.seen_files:
                self.seen_files.add(hash_key)
                self.emit(
                    "ai.run.log",
                    {
                        "run_id": self.run_id,
                        "message": f"Config updated: {rel_path}",
                        "level": "info",
                    },
                )

    def _detect_log_level(self, line: str) -> str:
        """Detect log level from line content."""
        line_lower = line.lower()
        if any(x in line_lower for x in ["error", "exception", "traceback", "failed"]):
            return "error"
        if any(x in line_lower for x in ["warning", "warn"]):
            return "warn"
        if any(x in line_lower for x in ["debug", "trace"]):
            return "debug"
        return "info"

    def _infer_stage(self, path: str) -> str:
        """Infer stage from file path."""
        if "stage_1" in path or "initial" in path:
            return "Stage_1"
        if "stage_2" in path or "baseline" in path:
            return "Stage_2"
        if "stage_3" in path or "research" in path:
            return "Stage_3"
        if "stage_4" in path or "ablation" in path:
            return "Stage_4"
        return "Stage_1"

    def _file_hash(self, file_path: Path) -> str:
        """Get file hash for change detection."""
        try:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
