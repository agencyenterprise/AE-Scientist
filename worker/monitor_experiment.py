#!/usr/bin/env python3
"""
Monitor experiment progress and emit events for live UI updates.
Watches experiment directory and emits events based on file changes.
"""
import glob
import hashlib
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import requests
from pymongo import MongoClient
from ulid import ULID

CONTROL_PLANE_URL = os.environ.get(
    "CONTROL_PLANE_URL", "https://ai-scientist-v2-production.up.railway.app"
)
POD_ID = os.environ.get("RUNPOD_POD_ID", "unknown")


class EventMonitor:
    def __init__(self, exp_dir: str, run_id: str):

        self.exp_dir = Path(exp_dir)
        self.run_id = run_id
        self.seen_nodes: set[str] = set()
        self.last_progress: dict[str, dict] = {}
        self.seq = 0
        self.mongo_client: MongoClient = MongoClient(os.environ.get("MONGODB_URL"))
        self.db = self.mongo_client["ai-scientist"]
        self.stage_start_times: dict[str, float] = {}
        self.log_positions: dict[str, int] = {}
        self.uploaded_artifacts: set[str] = set()

    def emit_event(self, event_type: str, data: dict) -> None:
        self.seq += 1
        event = {
            "specversion": "1.0",
            "id": str(ULID()),
            "source": f"monitor://pod/{POD_ID}",
            "type": event_type,
            "subject": f"run/{self.run_id}",
            "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "datacontenttype": "application/json",
            "data": {**data, "run_id": self.run_id},
            "extensions": {"seq": self.seq},
        }

        try:
            response = requests.post(
                f"{CONTROL_PLANE_URL}/api/ingest/event",
                json=event,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            print(f"✓ Emitted {event_type}")
        except Exception as e:
            print(f"✗ Failed to emit {event_type}: {e}")
            print(f"   Response: {response.text if 'response' in locals() else 'N/A'}")

    def check_stage_progress(self, stage_name: str, main_stage: str, max_iters: int) -> None:
        """Check stage progress files and emit events."""
        # Determine latest run directory (fallback to 0-run)
        logs_dir = self.exp_dir / "logs"
        run_dir = logs_dir / "0-run"
        try:
            candidates = [d for d in logs_dir.iterdir() if d.is_dir() and d.name.endswith("-run")]
            if candidates:

                def _run_number(p: Path) -> int:
                    try:
                        return int(p.name.split("-")[0])
                    except Exception:
                        return -1

                run_dir = sorted(candidates, key=_run_number, reverse=True)[0]
        except Exception:
            traceback.print_exc()

        stage_dir = run_dir / f"stage_{stage_name}" / "notes"
        progress_file = stage_dir / "stage_progress.json"

        if not progress_file.exists():
            return

        try:
            with open(progress_file) as f:
                progress = json.load(f)

            stage_key = f"{stage_name}"

            # Track stage start time
            if main_stage not in self.stage_start_times:
                self.stage_start_times[main_stage] = time.time()

            # Check if this is new progress
            if stage_key not in self.last_progress or progress != self.last_progress[stage_key]:
                self.last_progress[stage_key] = progress
                total = progress.get("total_nodes", 0)
                good = progress.get("good_nodes", 0)
                prog_val = min(good / max_iters, 1.0) if max_iters > 0 else 0.0

                # Calculate elapsed time for this stage
                elapsed_s = int(time.time() - self.stage_start_times[main_stage])
                elapsed_min = elapsed_s // 60
                elapsed_sec = elapsed_s % 60

                # Estimate remaining time
                eta_s = int(elapsed_s / prog_val - elapsed_s) if prog_val > 0.01 else None

                # Emit detailed progress event
                self.emit_event(
                    "ai.run.stage_progress",
                    {
                        "run_id": self.run_id,
                        "stage": main_stage,
                        "progress": prog_val,
                        "eta_s": eta_s,
                        "iteration": good,
                        "max_iterations": max_iters,
                        "good_nodes": good,
                        "buggy_nodes": progress.get("buggy_nodes", 0),
                        "total_nodes": total,
                        "best_metric": progress.get("best_metric"),
                    },
                )

                # Emit log event with details including time
                self.emit_event(
                    "ai.run.log",
                    {
                        "run_id": self.run_id,
                        "message": f"{main_stage}: {total} nodes ({progress.get('good_nodes', 0)} good, {progress.get('buggy_nodes', 0)} buggy) [{elapsed_min}m {elapsed_sec}s]",
                        "level": "info",
                    },
                )

                # Update currentStage in database with elapsed time
                self.db["runs"].update_one(
                    {"_id": self.run_id},
                    {
                        "$set": {
                            "currentStage": {"name": main_stage, "progress": prog_val},
                            f"stageTiming.{main_stage}.elapsed_s": elapsed_s,
                        }
                    },
                )

            # Check for new node summaries
            for node_file in stage_dir.glob("node_*_summary.json"):
                node_id = node_file.stem
                if node_id not in self.seen_nodes:
                    self.seen_nodes.add(node_id)
                    self.emit_event(
                        "ai.run.log",
                        {
                            "run_id": self.run_id,
                            "message": f"Node {node_id} completed",
                            "level": "info",
                        },
                    )

        except Exception as e:
            print(f"Warning: Error checking progress: {e}")

    def stream_logs(self) -> None:
        """Stream new log lines from experiment log files."""
        logs_dir = self.exp_dir / "logs"
        run_dir = logs_dir / "0-run"
        try:
            candidates = [d for d in logs_dir.iterdir() if d.is_dir() and d.name.endswith("-run")]
            if candidates:

                def _run_number(p: Path) -> int:
                    try:
                        return int(p.name.split("-")[0])
                    except Exception:
                        return -1

                run_dir = sorted(candidates, key=_run_number, reverse=True)[0]
        except Exception:
            traceback.print_exc()

        log_files = list(run_dir.glob("**/*.log"))

        for log_file in log_files:
            log_key = str(log_file.relative_to(self.exp_dir))

            if log_key not in self.log_positions:
                self.log_positions[log_key] = 0

            try:
                with open(log_file, "r") as f:
                    f.seek(self.log_positions[log_key])
                    new_lines = f.readlines()

                    if new_lines:
                        for line in new_lines[:20]:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                level = (
                                    "error"
                                    if "error" in line.lower() or "fail" in line.lower()
                                    else "info"
                                )
                                self.emit_event(
                                    "ai.run.log",
                                    {"run_id": self.run_id, "message": line[:500], "level": level},
                                )

                        self.log_positions[log_key] = f.tell()
            except Exception:
                pass

    def upload_artifacts(self) -> None:
        """Upload plots and other artifacts."""

        for plot_file in self.exp_dir.glob("**/*.png"):
            artifact_key = str(plot_file.relative_to(self.exp_dir))
            if artifact_key in self.uploaded_artifacts:
                continue

            try:
                with open(plot_file, "rb") as f:
                    file_bytes = f.read()

                filename = plot_file.name
                resp = requests.post(
                    f"{CONTROL_PLANE_URL}/api/runs/{self.run_id}/artifacts/presign",
                    json={"action": "put", "filename": filename, "content_type": "image/png"},
                    timeout=30,
                )
                resp.raise_for_status()
                presigned_url = resp.json()["url"]

                resp = requests.put(presigned_url, data=file_bytes, timeout=300)
                resp.raise_for_status()

                sha256 = hashlib.sha256(file_bytes).hexdigest()

                self.emit_event(
                    "ai.artifact.registered",
                    {
                        "run_id": self.run_id,
                        "key": f"runs/{self.run_id}/{filename}",
                        "bytes": len(file_bytes),
                        "sha256": sha256,
                        "content_type": "image/png",
                        "kind": "plot",
                    },
                )

                self.uploaded_artifacts.add(artifact_key)
                print(f"✓ Uploaded artifact: {filename}")
            except Exception as e:
                print(f"Warning: Failed to upload {artifact_key}: {e}")

    def monitor(self, interval: int = 5) -> None:
        """Monitor experiment directory and emit events."""
        print(f"🔍 Monitoring experiment: {self.exp_dir}")
        print(f"   Run ID: {self.run_id}")
        print(f"   Polling every {interval}s")
        print()

        stage_mapping = [
            ("1_initial_implementation_1_preliminary", "Stage_1", 14),
            ("2_baseline_tuning_1_first_attempt", "Stage_2", 8),
            ("3_creative_research_1_exploration", "Stage_3", 8),
            ("4_ablation_studies_1_first_attempt", "Stage_4", 14),
        ]

        try:
            while True:
                for substage, main_stage, max_iters in stage_mapping:
                    self.check_stage_progress(substage, main_stage, max_iters)

                self.stream_logs()
                self.upload_artifacts()
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python monitor_experiment.py <run_id> [exp_dir]")
        print("If exp_dir not provided, will auto-find latest folder for run_id")
        sys.exit(1)

    run_id = sys.argv[1]

    if len(sys.argv) >= 3:
        exp_dir = sys.argv[2]
    else:
        # Auto-find latest experiment directory for this run_id

        pattern = f"experiments/*_run_{run_id}"
        matches = sorted(glob.glob(pattern), reverse=True)
        if not matches:
            print(f"Error: No experiment directory found for run {run_id}")
            sys.exit(1)
        exp_dir = matches[0]
        print(f"Auto-detected experiment directory: {exp_dir}")

    if not os.path.exists(exp_dir):
        print(f"Error: Experiment directory not found: {exp_dir}")
        sys.exit(1)

    monitor = EventMonitor(exp_dir, run_id)
    monitor.monitor()


if __name__ == "__main__":
    main()
