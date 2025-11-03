"""
Centralized event emission module used by BOTH pod_worker and tests.
This ensures tests validate the exact same events the worker sends.
"""

from datetime import datetime
from typing import Any, Dict, Optional

import requests
from ulid import ULID


class CloudEventEmitter:
    """Emits CloudEvents to the control plane API."""

    def __init__(self, control_plane_url: str, source_id: str):
        self.control_plane_url = control_plane_url
        self.source_id = source_id
        self.seq_counter = 0

    def _create_envelope(self, event_type: str, run_id: str, data: Dict[str, Any]) -> Dict:
        """Create CloudEvents envelope."""
        self.seq_counter += 1

        return {
            "specversion": "1.0",
            "id": str(ULID()),
            "source": f"runpod://pod/{self.source_id}",
            "type": event_type,
            "subject": f"run/{run_id}",
            "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "datacontenttype": "application/json",
            "data": {**data, "run_id": run_id},
            "extensions": {"seq": self.seq_counter},
        }

    def emit(self, event_type: str, run_id: str, data: Dict[str, Any]) -> bool:
        """Emit a single event."""
        envelope = self._create_envelope(event_type, run_id, data)

        try:
            response = requests.post(
                f"{self.control_plane_url}/api/ingest/event",
                json=envelope,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to emit {event_type}: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"  Status: {e.response.status_code}")
                print(f"  Body: {e.response.text}")
            return False

    # Run Lifecycle Events
    def run_started(self, run_id: str, pod_id: str, gpu: str, region: str) -> bool:
        return self.emit(
            "ai.run.started",
            run_id,
            {"pod_id": pod_id, "gpu": gpu, "region": region, "image": "sakana:latest"},
        )

    def run_heartbeat(self, run_id: str) -> bool:
        return self.emit("ai.run.heartbeat", run_id, {})

    def run_completed(self, run_id: str, total_duration_s: int) -> bool:
        return self.emit("ai.run.completed", run_id, {"total_duration_s": total_duration_s})

    def run_failed(self, run_id: str, stage: str, code: str, message: str, traceback: str) -> bool:
        return self.emit(
            "ai.run.failed",
            run_id,
            {
                "stage": stage,
                "code": code,
                "message": message,
                "traceback": traceback,
                "retryable": False,
            },
        )

    # Stage Events
    def stage_started(self, run_id: str, stage: str, desc: str) -> bool:
        return self.emit("ai.run.stage_started", run_id, {"stage": stage, "desc": desc})

    def stage_progress(
        self,
        run_id: str,
        stage: str,
        progress: float,
        iteration: int,
        max_iterations: int,
        good_nodes: int,
        buggy_nodes: int,
        total_nodes: int,
        best_metric: Optional[str] = None,
        eta_s: Optional[int] = None,
    ) -> bool:
        # Clamp progress to [0, 1] to prevent validation errors
        progress = max(0.0, min(progress, 1.0))
        return self.emit(
            "ai.run.stage_progress",
            run_id,
            {
                "stage": stage,
                "progress": progress,
                "eta_s": eta_s,
                "iteration": iteration,
                "max_iterations": max_iterations,
                "good_nodes": good_nodes,
                "buggy_nodes": buggy_nodes,
                "total_nodes": total_nodes,
                "best_metric": best_metric,
            },
        )

    def stage_completed(self, run_id: str, stage: str, duration_s: int) -> bool:
        return self.emit(
            "ai.run.stage_completed", run_id, {"stage": stage, "duration_s": duration_s}
        )

    # Node Events
    def node_created(self, run_id: str, stage: str, node_id: str, parent_id: Optional[str]) -> bool:
        return self.emit(
            "ai.node.created", run_id, {"stage": stage, "node_id": node_id, "parent_id": parent_id}
        )

    def node_code_generated(self, run_id: str, stage: str, node_id: str, code_size: int) -> bool:
        return self.emit(
            "ai.node.code_generated",
            run_id,
            {"stage": stage, "node_id": node_id, "code_size_bytes": code_size},
        )

    def node_executing(self, run_id: str, stage: str, node_id: str) -> bool:
        return self.emit("ai.node.executing", run_id, {"stage": stage, "node_id": node_id})

    def node_completed(
        self,
        run_id: str,
        stage: str,
        node_id: str,
        is_buggy: bool,
        metric: Optional[str],
        exec_time_s: float,
    ) -> bool:
        return self.emit(
            "ai.node.completed",
            run_id,
            {
                "stage": stage,
                "node_id": node_id,
                "is_buggy": is_buggy,
                "metric": metric,
                "exec_time_s": exec_time_s,
            },
        )

    def node_selected_best(self, run_id: str, stage: str, node_id: str, metric: str) -> bool:
        return self.emit(
            "ai.node.selected_best", run_id, {"stage": stage, "node_id": node_id, "metric": metric}
        )

    # Logs
    def log(
        self, run_id: str, message: str, level: str = "info", source: Optional[str] = None
    ) -> bool:
        data = {"message": message, "level": level}
        if source:
            data["source"] = source
        return self.emit("ai.run.log", run_id, data)

    # Metrics
    def metric_computed(self, run_id: str, stage: str, name: str, value: float) -> bool:
        return self.emit(
            "ai.run.stage_metric", run_id, {"stage": stage, "name": name, "value": value}
        )

    # Artifacts
    def artifact_detected(self, run_id: str, path: str, type: str, size_bytes: int) -> bool:
        return self.emit(
            "ai.artifact.detected", run_id, {"path": path, "type": type, "size_bytes": size_bytes}
        )

    def artifact_registered(
        self, run_id: str, key: str, bytes: int, sha256: str, content_type: str, kind: str
    ) -> bool:
        return self.emit(
            "ai.artifact.registered",
            run_id,
            {
                "key": key,
                "bytes": bytes,
                "sha256": sha256,
                "content_type": content_type,
                "kind": kind,
            },
        )

    # Paper
    def paper_started(self, run_id: str) -> bool:
        return self.emit("ai.paper.started", run_id, {})

    def paper_generated(self, run_id: str, artifact_key: str) -> bool:
        return self.emit("ai.paper.generated", run_id, {"artifact_key": artifact_key})

    # Validation
    def validation_auto_started(self, run_id: str, model: str) -> bool:
        return self.emit(
            "ai.validation.auto_started", run_id, {"model": model, "rubric_version": "v1"}
        )

    def validation_auto_completed(
        self, run_id: str, verdict: str, scores: Dict, notes: str
    ) -> bool:
        return self.emit(
            "ai.validation.auto_completed",
            run_id,
            {"verdict": verdict, "scores": scores, "notes": notes},
        )
