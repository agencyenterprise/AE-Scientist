import argparse
import json
import logging
import os
import queue
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel
from research_pipeline.ai_scientist.artifact_manager import (  # type: ignore[import-not-found]
    ArtifactPublisher,
    ArtifactSpec,
)
from research_pipeline.ai_scientist.telemetry.event_persistence import (  # type: ignore[import-not-found]
    EventPersistenceManager,
    PersistableEvent,
    WebhookClient,
)

from app.services.research_pipeline.fake_runpod.webhooks import FakeRunPodWebhookPublisher
from app.services.research_pipeline.runpod.runpod_initialization import WORKSPACE_PATH

logger = logging.getLogger(__name__)

MIN_FAKE_RUNFILE_RUNNING_SECONDS = 15.0
MIN_FAKE_CODEX_OUTLIVES_RUNFILE_SECONDS = 5.0
FAKE_INITIALIZATION_STEP_DELAYS_SECONDS: list[tuple[str, float]] = [
    ("Cloning repository", 6.0),
    ("Installing OS packages", 8.0),
    ("Installing Python dependencies", 10.0),
    ("Configuring environment", 4.0),
]

# Global speed factor - set via --speed CLI argument (e.g., --speed 2 runs 2x faster)
_speed_factor: float = 1.0


class PodRecord(NamedTuple):
    id: str
    name: str
    gpu_type_requested: str
    desired_status: str
    public_ip: str
    port_mappings: Dict[str, str]
    cost_per_hr: float
    created_at: float
    ready_at: float
    run_id: str


class PodRequest(BaseModel):
    name: str
    imageName: str
    cloudType: str
    gpuCount: int
    gpuTypeIds: List[str]
    containerDiskInGb: int
    volumeInGb: int
    env: Dict[str, str]
    ports: List[str]
    dockerStartCmd: List[str]


class SkipStageRequest(BaseModel):
    run_id: str
    reason: str


class BillingRecord(NamedTuple):
    podId: str
    amount: float
    timeBilledMs: int


class TelemetryRecord(NamedTuple):
    path: str
    payload: Dict[str, object]
    received_at: float


class TerminateExecutionRequest(BaseModel):
    payload: str


class ExecutionRecord(NamedTuple):
    run_id: str
    stage_name: str
    run_type: str
    started_at: datetime
    status: str


app = FastAPI(title="Fake RunPod Server")
_pods: Dict[str, PodRecord] = {}
_lock = threading.Lock()
_telemetry_events: List[TelemetryRecord] = []
_runners_by_run_id: Dict[str, "FakeRunner"] = {}
_executions_by_id: Dict[str, ExecutionRecord] = {}


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required for fake RunPod server")
    return value


def _extract_bash_c_script(*, docker_start_cmd: List[str]) -> str:
    if len(docker_start_cmd) < 3:
        raise HTTPException(
            status_code=400, detail="dockerStartCmd must be like: ['bash', '-c', '<script>']"
        )
    if docker_start_cmd[0] != "bash" or docker_start_cmd[1] != "-c":
        raise HTTPException(
            status_code=400, detail="dockerStartCmd must be like: ['bash', '-c', '<script>']"
        )
    script = docker_start_cmd[2]
    if not script:
        raise HTTPException(status_code=400, detail="dockerStartCmd script missing")
    return script


def _parse_env_file_from_docker_start_cmd(*, docker_start_cmd: List[str]) -> Dict[str, str]:
    script = _extract_bash_c_script(docker_start_cmd=docker_start_cmd)

    # Expect a heredoc of the form:
    #   cat > .env << 'EOF'
    #   KEY=value
    #   ...
    #   EOF
    #
    # Some callers escape quotes inside the string (e.g. << \'EOF\'), so we allow a
    # leading backslash before quotes.
    match = re.search(
        r"cat\s+>\s+\.env\s+<<\s*\\?['\"]?EOF\\?['\"]?\n(?P<body>[\s\S]*?)\nEOF\b",
        script,
    )
    if match is None:
        raise HTTPException(status_code=400, detail="Could not find .env heredoc in dockerStartCmd")

    env: Dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        env[key] = value
    return env


def _build_pod_response(record: PodRecord) -> Dict[str, object]:
    return {
        "consumerUserId": "user_2mIwrbzAHBibbeosezqlYwi7fpW",
        "containerDiskInGb": 30,
        "createdAt": "2025-12-16 17:44:56.726 +0000 UTC",
        "RUN_ID": record.run_id,
        "gpuCount": 1,
        "imageName": "newtonsander/runpod_pytorch_texdeps:v1",
        "lastStartedAt": "2025-12-16 17:44:56.715 +0000 UTC",
        "lastStatusChange": "Rented by User: Tue Dec 16 2025 17:44:56 GMT+0000 (Coordinated Universal Time)",
        "machine": {
            "dataCenterId": "US-NC-1",
            "diskThroughputMBps": 9912,
            "gpuTypeId": record.gpu_type_requested,
            "location": "US",
            "maxDownloadSpeedMbps": 9184,
            "maxUploadSpeedMbps": 2586,
            "secureCloud": True,
            "supportPublicIp": True,
            "reservedCountVersion": 201404,
        },
        "machineId": "9obq8gv22tj8",
        "memoryInGb": 141,
        "ports": ["22/tcp"],
        "templateId": "",
        "vcpuCount": 16,
        "volumeInGb": 70,
        "name": record.name,
        "id": record.id,
        "volumeMountPath": WORKSPACE_PATH,
        "desiredStatus": record.desired_status,
        "publicIp": record.public_ip,
        "portMappings": record.port_mappings,
        "costPerHr": record.cost_per_hr,
    }


def _schedule_ready_transition(record: PodRecord, delay_seconds: int) -> None:
    def _transition() -> None:
        time.sleep(delay_seconds / _speed_factor)
        with _lock:
            current = _pods.get(record.id)
            if current is None:
                logger.warning("Ready transition skipped; pod %s not found", record.id)
                return
            logger.info("Transitioning pod %s to RUNNING", record.id)
            updated = PodRecord(
                id=current.id,
                name=current.name,
                gpu_type_requested=current.gpu_type_requested,
                desired_status="RUNNING",
                public_ip="127.0.0.1",
                port_mappings={"22": "0"},
                cost_per_hr=current.cost_per_hr,
                created_at=current.created_at,
                ready_at=time.time(),
                run_id=current.run_id,
            )
            _pods[record.id] = updated

    thread = threading.Thread(target=_transition, name=f"fake-ready-{record.id}", daemon=True)
    thread.start()


def _start_fake_runner(
    *,
    record: PodRecord,
    webhook_url: str,
    webhook_token: str,
) -> "FakeRunner":
    runner = FakeRunner(
        run_id=record.run_id,
        pod_id=record.id,
        webhook_url=webhook_url,
        webhook_token=webhook_token,
    )
    thread = threading.Thread(target=runner.run, name=f"fake-runner-{record.run_id}", daemon=True)
    thread.start()
    return runner


@app.post("/pods")
def create_pod(request: PodRequest = Body(...)) -> Dict[str, object]:
    logger.info(
        "Received create_pod request: name=%s gpuTypeIds=%s", request.name, request.gpuTypeIds
    )
    if not request.gpuTypeIds:
        raise HTTPException(status_code=400, detail="gpuTypeIds required")

    parsed_env = _parse_env_file_from_docker_start_cmd(docker_start_cmd=request.dockerStartCmd)

    run_id = parsed_env.get("RUN_ID")
    if not run_id:
        raise HTTPException(status_code=400, detail="RUN_ID missing from dockerStartCmd .env")
    telemetry_webhook_url = parsed_env.get("TELEMETRY_WEBHOOK_URL")
    telemetry_webhook_token = parsed_env.get("TELEMETRY_WEBHOOK_TOKEN")
    if not telemetry_webhook_url or not telemetry_webhook_token:
        raise HTTPException(
            status_code=400, detail="TELEMETRY_WEBHOOK_* missing from dockerStartCmd .env"
        )
    pod_id = f"fake-{uuid.uuid4()}"
    created_at = time.time()
    record = PodRecord(
        id=pod_id,
        name=request.name,
        gpu_type_requested=request.gpuTypeIds[0],
        desired_status="PENDING",
        public_ip="",
        port_mappings={},
        cost_per_hr=0.89,
        created_at=created_at,
        ready_at=0.0,
        run_id=run_id,
    )
    with _lock:
        _pods[pod_id] = record
    logger.info("Created fake pod %s for run %s", pod_id, run_id)
    _schedule_ready_transition(record, delay_seconds=1)
    runner = _start_fake_runner(
        record=record,
        webhook_url=telemetry_webhook_url,
        webhook_token=telemetry_webhook_token,
    )
    with _lock:
        _runners_by_run_id[record.run_id] = runner
    return _build_pod_response(record)


@app.get("/pods/{pod_id}")
def get_pod(pod_id: str) -> Dict[str, object]:
    with _lock:
        record = _pods.get(pod_id)
    if record is None:
        raise HTTPException(status_code=404, detail="pod not found")
    return _build_pod_response(record)


@app.delete("/pods/{pod_id}")
def delete_pod(pod_id: str) -> Dict[str, str]:
    logger.info("Received delete_pod request: pod_id=%s", pod_id)
    return {"status": "deleted"}


@app.get("/billing/pods")
def get_billing_summary(
    podId: str = Query(...), grouping: str = Query(...)
) -> List[Dict[str, object]]:
    if grouping != "podId":
        raise HTTPException(status_code=400, detail="Unsupported grouping")
    with _lock:
        record = _pods.get(podId)
    if record is None:
        logger.warning("No record found for pod %s", podId)
        return []
    return [
        {
            "amount": 1.4341899856226519,
            "timeBilledMs": 5707585,
            "diskSpaceBilledGB": 600,
            "podId": record.id,
            "time": "2025-12-13 00:00:00",
        }
    ]


@app.post("/graphql")
def graphql_query(body: Dict[str, object] = Body(...)) -> Dict[str, object]:
    query = body.get("query")
    variables = body.get("variables", {})
    if "podHostId" in json.dumps(query):
        return {"data": {"pod": {"machine": {"podHostId": "fake-host"}}}}
    return {"data": {}, "variables": variables}


@app.post("/skip-stage")
def skip_stage(request: SkipStageRequest = Body(...)) -> Dict[str, object]:
    with _lock:
        runner = _runners_by_run_id.get(request.run_id)
    if runner is None:
        raise HTTPException(status_code=404, detail="run not found")
    runner.request_stage_skip(reason=request.reason)
    return {}


@app.post("/terminate/{execution_id}")
def terminate_execution(
    execution_id: str,
    request: TerminateExecutionRequest = Body(...),
) -> Dict[str, object]:
    with _lock:
        record = _executions_by_id.get(execution_id)
        runner = _runners_by_run_id.get(record.run_id) if record is not None else None

    if record is None:
        raise HTTPException(status_code=404, detail="execution not found")
    if runner is None:
        raise HTTPException(status_code=404, detail="run not found")

    status_code, detail = runner.terminate_execution(
        execution_id=execution_id,
        payload=request.payload,
    )
    if status_code == 200:
        return {}
    raise HTTPException(status_code=status_code, detail=detail)


@app.post("/telemetry/run-started", status_code=204)
def telemetry_run_started(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/run-started", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/run-finished", status_code=204)
def telemetry_run_finished(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/run-finished", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/heartbeat", status_code=204)
def telemetry_heartbeat(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/heartbeat", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/hw-stats", status_code=204)
def telemetry_hw_stats(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/hw-stats", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/stage-progress", status_code=204)
def telemetry_stage_progress(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/stage-progress", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/substage-completed", status_code=204)
def telemetry_substage(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(
            path="/telemetry/substage-completed", payload=payload, received_at=time.time()
        )
    )


@app.post("/telemetry/gpu-shortage", status_code=204)
def telemetry_gpu_shortage(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/gpu-shortage", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/paper-generation-progress", status_code=204)
def telemetry_paper_generation_progress(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(
            path="/telemetry/paper-generation-progress", payload=payload, received_at=time.time()
        )
    )


@app.post("/telemetry/best-node-selection", status_code=204)
def telemetry_best_node_selection(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(
            path="/telemetry/best-node-selection",
            payload=payload,
            received_at=time.time(),
        )
    )


@app.get("/telemetry")
def list_telemetry() -> List[Dict[str, object]]:
    return [
        {
            "path": record.path,
            "payload": record.payload,
            "received_at": record.received_at,
        }
        for record in _telemetry_events
    ]


class LocalPersistence:
    def __init__(self, webhook_client: WebhookClient) -> None:
        self.queue: "queue.SimpleQueue[PersistableEvent | None]" = queue.SimpleQueue()
        self._webhook_client = webhook_client
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._drain_queue,
            name="LocalPersistenceWorker",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self.queue.put(None)  # Sentinel to wake up the thread
            self._thread.join(timeout=5)

    def _drain_queue(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            try:
                self._webhook_client.publish(kind=item.kind, payload=item.data)
            except Exception:
                logger.exception("Failed to publish event via webhook; dropping event.")


class FakeRunner:
    def __init__(
        self,
        run_id: str,
        pod_id: str,
        webhook_url: str,
        webhook_token: str,
    ) -> None:
        self._run_id = run_id
        self._pod_id = pod_id
        self._webhook_url = webhook_url
        self._webhook_token = webhook_token
        self._iterations_per_stage = 3
        self._stage_plan: list[tuple[str, int]] = [
            ("1_initial_implementation", 10),
            ("2_baseline_tuning", 5),
            ("3_creative_research", 5),
            ("4_ablation_studies", 5),
        ]
        self._heartbeat_interval_seconds = 10
        self._periodic_log_interval_seconds = 15
        webhook_client = WebhookClient(
            base_url=self._webhook_url,
            token=self._webhook_token,
            run_id=self._run_id,
        )
        # Fake runner uses LocalPersistence (webhook-only, no database)
        self._persistence: EventPersistenceManager | LocalPersistence = LocalPersistence(
            webhook_client
        )
        self._webhook_client: Any = webhook_client
        self._heartbeat_stop = threading.Event()
        self._log_stop = threading.Event()
        self._log_thread: Optional[threading.Thread] = None
        self._data_dir = Path(__file__).parent / "data"
        self._plot_filename: str | None = None
        self._random_exec_time_seconds = 12.0
        self._code_event_delay_seconds = 12.0
        self._stage_skip_windows: Dict[str, Tuple[str, str]] = {}
        self._webhooks = FakeRunPodWebhookPublisher(
            client=self._webhook_client, run_id=self._run_id
        )
        self._stage_skip_requested = threading.Event()
        self._stage_skip_reason: str | None = None
        self._stage_skip_lock = threading.Lock()

    def _sleep(self, seconds: float) -> None:
        """Sleep for the given duration, adjusted by the global speed factor."""
        adjusted = seconds / _speed_factor
        time.sleep(adjusted)

    def _adjusted_timeout(self, seconds: float) -> float:
        """Return the timeout adjusted by the global speed factor."""
        return seconds / _speed_factor

    def request_stage_skip(self, *, reason: str) -> None:
        with self._stage_skip_lock:
            self._stage_skip_reason = reason
        self._stage_skip_requested.set()

    def _consume_stage_skip_request(self) -> str | None:
        if not self._stage_skip_requested.is_set():
            return None
        self._stage_skip_requested.clear()
        with self._stage_skip_lock:
            reason = self._stage_skip_reason
            self._stage_skip_reason = None
        return reason

    def _wait_or_skip(self, *, timeout_seconds: float) -> str | None:
        if not self._stage_skip_requested.wait(timeout=self._adjusted_timeout(timeout_seconds)):
            return None
        return self._consume_stage_skip_request()

    def terminate_execution(self, *, execution_id: str, payload: str) -> tuple[int, str]:
        with _lock:
            record = _executions_by_id.get(execution_id)
            if record is None:
                return 404, "Unknown execution_id"
            if record.run_id != self._run_id:
                return 404, "Unknown execution_id"
            if record.status in ("success", "terminated"):
                return 409, "Execution already completed or terminating"
            if record.status == "terminating":
                return 409, "Execution already completed or terminating"
            _executions_by_id[execution_id] = record._replace(status="terminating")

        now = datetime.now(timezone.utc)
        exec_time = max(0.0, (now - record.started_at).total_seconds())
        self._enqueue_event(
            kind="run_log",
            data={
                "message": f"Termination requested for execution {execution_id}: {payload}",
                "level": "warn",
            },
        )
        # Publish termination webhook
        try:
            self._webhooks.publish_run_completed(
                {
                    "execution_id": execution_id,
                    "stage_name": record.stage_name,
                    "run_type": record.run_type,
                    "status": "failed",
                    "exec_time": exec_time,
                    "completed_at": now.isoformat(),
                }
            )
        except Exception:  # noqa: BLE001 - fake runner best-effort
            logger.exception(
                "Failed to publish terminated execution webhook for %s (stage=%s)",
                execution_id,
                record.stage_name,
            )
        with _lock:
            latest = _executions_by_id.get(execution_id)
            if latest is not None and latest.run_id == self._run_id:
                _executions_by_id[execution_id] = latest._replace(status="terminated")
        return 200, ""

    def run(self) -> None:
        logger.info(
            "[FakeRunner %s] Starting simulation for pod %s", self._run_id[:8], self._pod_id[:13]
        )
        self._persistence.start()
        logger.info("FakeRunner started for run_id=%s pod_id=%s", self._run_id, self._pod_id)
        self._simulate_initialization()
        self._publish_run_started()
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name=f"heartbeat-{self._run_id}", daemon=True
        )
        heartbeat_thread.start()
        log_thread = threading.Thread(
            target=self._log_generator_loop, name=f"loggen-{self._run_id}", daemon=True
        )
        log_thread.start()
        self._log_thread = log_thread
        logger.info(
            "[FakeRunner %s] Heartbeat thread started (interval=%ds)",
            self._run_id[:8],
            self._heartbeat_interval_seconds,
        )
        try:
            self._publish_fake_plot_artifact()
            self._emit_fake_hw_stats()
            self._emit_progress_flow()
            self._emit_fake_token_usage()
            self._publish_fake_artifact()
            self._emit_fake_figure_reviews()
            self._emit_fake_review()
            self._publish_run_finished(True, "")
        finally:
            self._heartbeat_stop.set()
            self._log_stop.set()
            heartbeat_thread.join(timeout=self._heartbeat_interval_seconds + 1)
            if self._log_thread is not None:
                self._log_thread.join(timeout=self._periodic_log_interval_seconds + 1)
            self._persistence.stop()
            logger.info("FakeRunner stopped for run_id=%s", self._run_id)
            logger.info("[FakeRunner %s] Simulation complete", self._run_id[:8])

    def _simulate_initialization(self) -> None:
        if self._webhook_client is None:
            total = sum(delay for _, delay in FAKE_INITIALIZATION_STEP_DELAYS_SECONDS)
            self._sleep(total)
            return
        for message, delay_seconds in FAKE_INITIALIZATION_STEP_DELAYS_SECONDS:
            try:
                self._webhook_client.publish_initialization_progress(message=message)
            except Exception:  # noqa: BLE001 - fake runner best-effort
                logger.exception(
                    "[FakeRunner %s] Failed to publish initialization progress (%s)",
                    self._run_id[:8],
                    message,
                )
            self._sleep(delay_seconds)

    def _heartbeat_loop(self) -> None:
        webhook_client = self._webhook_client
        while not self._heartbeat_stop.is_set():
            logger.debug("Heartbeat tick for run %s", self._run_id)
            self._persistence.queue.put(
                PersistableEvent(kind="run_log", data={"message": "heartbeat", "level": "debug"})
            )
            try:
                if webhook_client is not None:
                    webhook_client.publish_heartbeat()
            except Exception:
                logger.exception("Failed to publish heartbeat for run %s", self._run_id)
            self._heartbeat_stop.wait(
                timeout=self._adjusted_timeout(self._heartbeat_interval_seconds)
            )

    def _log_generator_loop(self) -> None:
        counter = 1
        while not self._log_stop.is_set():
            message = f"[FakeRunner {self._run_id[:8]}] periodic log #{counter}"
            payload = {"message": message, "level": "info"}
            try:
                self._persistence.queue.put(PersistableEvent(kind="run_log", data=payload))
            except Exception:
                logger.exception("Failed to enqueue periodic log for run %s", self._run_id)
            counter += 1
            self._log_stop.wait(timeout=self._adjusted_timeout(self._periodic_log_interval_seconds))

    def _enqueue_event(self, *, kind: str, data: dict[str, Any]) -> None:
        try:
            self._persistence.queue.put(PersistableEvent(kind=kind, data=data))
        except Exception:
            logger.exception("Failed to enqueue %s event for run %s", kind, self._run_id)

    def _emit_stage_skip_window_event(self, *, stage_name: str, state: str, reason: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {
            "stage": stage_name,
            "state": state,
            "timestamp": timestamp,
            "reason": reason,
        }
        logger.info(
            "[FakeRunner %s] Stage skip window %s for %s",
            self._run_id[:8],
            state,
            stage_name,
        )
        try:
            self._persistence.queue.put(
                PersistableEvent(
                    kind="stage_skip_window",
                    data=payload,
                )
            )
            logger.debug(
                "[FakeRunner %s] Enqueued stage_skip_window event (stage=%s state=%s)",
                self._run_id[:8],
                stage_name,
                state,
            )
        except Exception:
            logger.exception(
                "[FakeRunner %s] Failed to enqueue stage skip window event for stage %s",
                self._run_id[:8],
                stage_name,
            )
        self._webhooks.publish_stage_skip_window(payload)

    def _emit_code_execution_events(self, *, stage_name: str, iteration: int) -> None:
        execution_id = f"{stage_name}-{iteration + 1}-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)
        logger.debug(
            "[FakeRunner %s] Emitting code execution events execution_id=%s stage=%s iteration=%s",
            self._run_id[:8],
            execution_id,
            stage_name,
            iteration + 1,
        )
        fake_task_markdown = (
            f"# Fake Codex task for {stage_name} iteration {iteration + 1}\n\n"
            "This simulates the markdown prompt we send to Codex.\n\n"
            "## Objective\n"
            "Write `runfile.py` with a minimal experiment and then execute it.\n\n"
            "## Files\n"
            "- `runfile.py`: main script to execute\n"
        )
        fake_runfile_code = (
            "\n\n"
            "def main() -> None:\n"
            "    print('Hello from fake runfile execution')\n\n"
            "main()\n"
        )
        codex_run_type = "codex_execution"
        runfile_run_type = "runfile_execution"
        with _lock:
            _executions_by_id[execution_id] = ExecutionRecord(
                run_id=self._run_id,
                stage_name=stage_name,
                run_type=codex_run_type,
                started_at=started_at,
                status="running",
            )
        self._webhooks.publish_running_code(
            {
                "execution_id": execution_id,
                "stage_name": stage_name,
                "run_type": codex_run_type,
                "code": fake_task_markdown,
                "started_at": started_at.isoformat(),
            }
        )

        # Emit Codex JSONL-like events so the UI can show Codex activity.
        self._emit_codex_events(stage_name=stage_name, node_index=iteration)

        # Simulate the moment when Codex starts executing the runfile.
        self._sleep(1)
        runfile_started_at = datetime.now(timezone.utc)
        self._webhooks.publish_running_code(
            {
                "execution_id": execution_id,
                "stage_name": stage_name,
                "run_type": runfile_run_type,
                "code": fake_runfile_code,
                "started_at": runfile_started_at.isoformat(),
            }
        )

        # Keep the "runfile execution" shorter than the overall Codex session.
        runfile_exec_time = max(
            MIN_FAKE_RUNFILE_RUNNING_SECONDS, float(self._random_exec_time_seconds) * 0.4
        )
        logger.debug(
            "[FakeRunner %s] Starting runfile execution execution_id=%s running_for_s=%.1f",
            self._run_id[:8],
            execution_id,
            runfile_exec_time / _speed_factor,
        )
        self._sleep(runfile_exec_time)
        runfile_completed_at = datetime.now(timezone.utc)
        runfile_exec_time = max(0.0, (runfile_completed_at - runfile_started_at).total_seconds())
        logger.debug(
            "[FakeRunner %s] Completing runfile execution execution_id=%s completed_at=%s",
            self._run_id[:8],
            execution_id,
            runfile_completed_at.isoformat(),
        )
        self._webhooks.publish_run_completed(
            {
                "execution_id": execution_id,
                "stage_name": stage_name,
                "run_type": runfile_run_type,
                "status": "success",
                "exec_time": runfile_exec_time,
                "completed_at": runfile_completed_at.isoformat(),
            }
        )

        # Ensure codex_execution always outlives runfile_execution.
        self._sleep(MIN_FAKE_CODEX_OUTLIVES_RUNFILE_SECONDS)
        completed_at = datetime.now(timezone.utc)
        exec_time = max(0.0, (completed_at - started_at).total_seconds())
        logger.debug(
            "[FakeRunner %s] Completing codex execution execution_id=%s completed_at=%s",
            self._run_id[:8],
            execution_id,
            completed_at.isoformat(),
        )
        self._webhooks.publish_run_completed(
            {
                "execution_id": execution_id,
                "stage_name": stage_name,
                "run_type": codex_run_type,
                "status": "success",
                "exec_time": exec_time,
                "completed_at": completed_at.isoformat(),
            }
        )
        with _lock:
            existing = _executions_by_id.get(execution_id)
            if existing is not None:
                _executions_by_id[execution_id] = existing._replace(status="success")

    def _emit_codex_events(self, *, stage_name: str, node_index: int) -> None:
        item_id = f"item_{uuid.uuid4().hex[:6]}"
        item_event = {
            "type": "item.started",
            "item": {
                "id": item_id,
                "type": "command_execution",
                "command": "bash -lc python runfile.py",
                "status": "in_progress",
            },
        }
        self._enqueue_event(
            kind="codex_event",
            data={
                "stage": stage_name,
                "node": node_index,
                "event_type": "item.started",
                "event_content": item_event,
            },
        )
        item_completed_event = {
            "type": "item.completed",
            "item": {
                "id": item_id,
                "type": "command_execution",
                "command": "bash -lc python runfile.py",
                "status": "completed",
                "exit_code": 0,
            },
        }
        self._enqueue_event(
            kind="codex_event",
            data={
                "stage": stage_name,
                "node": node_index,
                "event_type": "item.completed",
                "event_content": item_completed_event,
            },
        )
        turn_event = {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1200,
                "cached_input_tokens": 800,
                "output_tokens": 250,
            },
        }
        self._enqueue_event(
            kind="codex_event",
            data={
                "stage": stage_name,
                "node": node_index,
                "event_type": "turn.completed",
                "event_content": turn_event,
            },
        )

    def _emit_progress_flow(self) -> None:
        total_iterations = len(self._stage_plan) * self._iterations_per_stage
        current_iter = 0
        for stage_index, (stage_name, max_iterations) in enumerate(self._stage_plan):
            logger.info(
                "[FakeRunner %s] Stage %d/%d: %s",
                self._run_id[:8],
                stage_index + 1,
                len(self._stage_plan),
                stage_name,
            )
            self._emit_stage_skip_window_event(
                stage_name=stage_name,
                state="opened",
                reason="Fake runner marked stage as skippable.",
            )
            stage_skipped = False
            stage_skip_reason: str | None = None
            iterations_to_emit = min(self._iterations_per_stage, max_iterations)
            for iteration in range(iterations_to_emit):
                pending_skip_reason = self._consume_stage_skip_request()
                if pending_skip_reason is not None:
                    stage_skipped = True
                    stage_skip_reason = pending_skip_reason
                    logger.info(
                        "[FakeRunner %s] Skip requested for stage %s: %s",
                        self._run_id[:8],
                        stage_name,
                        stage_skip_reason,
                    )
                    break
                current_iter += 1
                progress = (iteration + 1) / max_iterations
                logger.debug(
                    "Emitting progress run=%s stage=%s iteration=%s progress=%.2f",
                    self._run_id,
                    stage_name,
                    iteration + 1,
                    progress,
                )
                self._emit_code_execution_events(stage_name=stage_name, iteration=iteration)
                self._enqueue_event(
                    kind="run_stage_progress",
                    data={
                        "stage": stage_name,
                        "iteration": iteration + 1,
                        "max_iterations": max_iterations,
                        "progress": progress,
                        "total_nodes": 10 + iteration,
                        "buggy_nodes": iteration,
                        "good_nodes": 9 - iteration,
                        "best_metric": f"metric-{progress:.2f}",
                        "eta_s": int((total_iterations - current_iter) * 20),
                        "latest_iteration_time_s": 20,
                    },
                )
                self._enqueue_event(
                    kind="run_log",
                    data={
                        "message": f"{stage_name} iteration {iteration + 1} complete",
                        "level": "info",
                    },
                )
                # Mid-stage tree viz emit on second iteration (iteration index 1)
                if iteration == 1:
                    try:
                        self._store_tree_viz(stage_number=stage_index + 1, version=iteration + 1)
                    except Exception:
                        logger.exception(
                            "Failed to store mid-stage tree viz for stage %s iteration %s",
                            stage_name,
                            iteration + 1,
                        )
                pending_skip_reason = self._wait_or_skip(timeout_seconds=20)
                if pending_skip_reason is not None:
                    stage_skipped = True
                    stage_skip_reason = pending_skip_reason
                    logger.info(
                        "[FakeRunner %s] Skip requested for stage %s during wait: %s",
                        self._run_id[:8],
                        stage_name,
                        stage_skip_reason,
                    )
                    break
                logger.info(
                    "[FakeRunner %s]   Iteration %d/%d complete (%.0f%% overall)",
                    self._run_id[:8],
                    iteration + 1,
                    iterations_to_emit,
                    (current_iter / total_iterations) * 100,
                )
            if stage_skipped:
                effective_skip_reason = stage_skip_reason or "Stage skipped by operator."
                self._enqueue_event(
                    kind="run_log",
                    data={
                        "message": f"Skipping stage {stage_name}: {effective_skip_reason}",
                        "level": "warn",
                    },
                )
                summary = {
                    "goals": f"Goals for {stage_name}",
                    "feedback": effective_skip_reason,
                    "good_nodes": 0,
                    "best_metric": None,
                    "buggy_nodes": 0,
                    "total_nodes": 0,
                    "llm_summary": f"Stage {stage_name} skipped.",
                }
                self._enqueue_event(
                    kind="substage_completed",
                    data={
                        "stage": stage_name,
                        "main_stage_number": stage_index + 1,
                        "reason": "skipped",
                        "summary": summary,
                    },
                )
                try:
                    self._enqueue_event(
                        kind="substage_summary",
                        data={
                            "stage": stage_name,
                            "summary": summary,
                        },
                    )
                except Exception:
                    logger.exception(
                        "Failed to enqueue skipped-stage substage summary for stage %s",
                        stage_name,
                    )
                self._emit_stage_skip_window_event(
                    stage_name=stage_name,
                    state="closed",
                    reason=effective_skip_reason,
                )
                continue
            self._emit_fake_best_node(stage_name=stage_name, stage_index=stage_index)
            summary = {
                "goals": f"Goals for {stage_name}",
                "feedback": "Reached max iterations",
                "good_nodes": 2,
                "best_metric": f"Metrics(fake metric for {stage_name})",
                "buggy_nodes": 1,
                "total_nodes": 3,
                "llm_summary": f"Stage {stage_name} completed with synthetic findings.",
            }
            logger.info("Emitting substage_completed for stage %s", stage_name)
            self._enqueue_event(
                kind="substage_completed",
                data={
                    "stage": stage_name,
                    "main_stage_number": stage_index + 1,
                    "reason": "completed",
                    "summary": summary,
                },
            )
            try:
                self._enqueue_event(
                    kind="substage_summary",
                    data={
                        "stage": stage_name,
                        "summary": summary,
                    },
                )
            except Exception:
                logger.exception("Failed to enqueue fake substage summary for stage %s", stage_name)
            logger.info(
                "[FakeRunner %s] Stage %d/%d complete",
                self._run_id[:8],
                stage_index + 1,
                len(self._stage_plan),
            )
            self._emit_stage_skip_window_event(
                stage_name=stage_name,
                state="closed",
                reason="Stage completed in fake runner.",
            )

        # Stage 5: Paper Generation
        logger.info("[FakeRunner %s] Starting paper generation (Stage 5)", self._run_id[:8])
        self._emit_paper_generation_flow()

    def _emit_paper_generation_flow(self) -> None:
        """Emit Stage 5 paper generation progress events."""
        # Define the paper generation steps with their substeps
        paper_steps: list[tuple[str, list[str], dict[str, object]]] = [
            (
                "plot_aggregation",
                ["collecting_figures", "validating_plots", "generating_captions"],
                {"figures_collected": 8, "valid_plots": 7},
            ),
            (
                "citation_gathering",
                ["searching_literature", "filtering_relevant", "formatting_citations"],
                {"citations_found": 15, "relevant_citations": 12},
            ),
            (
                "paper_writeup",
                [
                    "writing_abstract",
                    "writing_introduction",
                    "writing_methodology",
                    "writing_results",
                    "writing_discussion",
                    "writing_conclusion",
                ],
                {"sections_completed": 6, "word_count": 4500},
            ),
            (
                "paper_review",
                ["review_1", "review_2", "review_3"],
                {
                    "avg_score": 7.2,
                    "review_scores": [7.0, 7.5, 7.1],
                    "strengths": ["novel approach", "thorough experiments"],
                    "weaknesses": ["limited comparison", "minor clarity issues"],
                },
            ),
        ]

        total_steps = len(paper_steps)
        for step_idx, (step_name, substeps, step_details) in enumerate(paper_steps):
            logger.info(
                "[FakeRunner %s] Paper step %d/%d: %s",
                self._run_id[:8],
                step_idx + 1,
                total_steps,
                step_name,
            )
            for substep_idx, substep_name in enumerate(substeps):
                step_progress = (substep_idx + 1) / len(substeps)
                overall_progress = (step_idx + step_progress) / total_steps

                self._enqueue_event(
                    kind="paper_generation_progress",
                    data={
                        "step": step_name,
                        "substep": substep_name,
                        "progress": overall_progress,
                        "step_progress": step_progress,
                        "details": {
                            **step_details,
                            "current_substep": substep_idx + 1,
                            "total_substeps": len(substeps),
                        },
                    },
                )
                self._enqueue_event(
                    kind="run_log",
                    data={
                        "message": f"Paper generation: {step_name} - {substep_name}",
                        "level": "info",
                    },
                )
                # Shorter delay for paper generation steps (5s instead of 20s)
                self._sleep(5)
                logger.info(
                    "[FakeRunner %s]   %s complete (%.0f%% step)",
                    self._run_id[:8],
                    substep_name,
                    step_progress * 100,
                )

        # Log completion
        self._enqueue_event(
            kind="run_log",
            data={
                "message": "Paper generation completed",
                "level": "info",
            },
        )
        logger.info("[FakeRunner %s] Paper generation complete", self._run_id[:8])

    def _emit_fake_token_usage(self) -> None:
        """Emit fake token usage events to exercise the token_usage webhook."""
        stages = ["1_initial_implementation", "2_baseline_tuning", "3_creative_research"]
        for stage in stages:
            payload = {
                "provider": "openai",
                "model": "gpt-4o",
                "input_tokens": 15000 + hash(stage) % 5000,
                "output_tokens": 3000 + hash(stage) % 1000,
                "cached_input_tokens": 8000 + hash(stage) % 2000,
            }
            try:
                self._webhooks.publish_token_usage(payload)
            except Exception:
                logger.exception(
                    "[FakeRunner %s] Failed to publish token_usage for stage %s",
                    self._run_id[:8],
                    stage,
                )
        logger.info(
            "[FakeRunner %s] Posted token_usage webhooks for %d stages",
            self._run_id[:8],
            len(stages),
        )

    def _emit_fake_hw_stats(self) -> None:
        """Emit fake hardware stats to exercise the hw-stats webhook."""
        partitions = [
            {"partition": "/", "total_bytes": 500_000_000_000, "used_bytes": 150_000_000_000},
            {
                "partition": "/workspace",
                "total_bytes": 200_000_000_000,
                "used_bytes": 50_000_000_000,
            },
        ]
        try:
            if self._webhook_client is not None:
                self._webhook_client.publish_hw_stats(partitions=partitions)
                logger.info("[FakeRunner %s] Posted hw-stats webhook", self._run_id[:8])
        except Exception:
            logger.exception("[FakeRunner %s] Failed to publish hw-stats", self._run_id[:8])

    def _emit_fake_figure_reviews(self) -> None:
        """Emit fake VLM figure reviews to exercise the figure_reviews webhook."""
        fake_reviews = [
            {
                "figure_name": "Figure 1",
                "img_description": "A line plot showing training loss curves over 100 epochs. The blue line represents the baseline model while the orange line shows our improved method.",
                "img_review": "The figure clearly demonstrates the convergence behavior of both methods. The improved method shows faster convergence and lower final loss.",
                "caption_review": "Caption accurately describes the plot contents and provides context for interpretation.",
                "figrefs_review": "Figure is appropriately referenced in Section 3.2 when discussing training dynamics.",
                "source_path": "plots/loss_curves.png",
            },
            {
                "figure_name": "Figure 2",
                "img_description": "A bar chart comparing accuracy metrics across three datasets: MNIST, CIFAR-10, and ImageNet.",
                "img_review": "Clear visualization of comparative performance. Error bars would improve the figure by showing statistical significance.",
                "caption_review": "Caption is informative but could benefit from including exact numerical values.",
                "figrefs_review": "Referenced correctly in the results section.",
                "source_path": "plots/accuracy_comparison.png",
            },
            {
                "figure_name": "Figure 3",
                "img_description": "Architecture diagram showing the neural network structure with attention mechanisms.",
                "img_review": "Well-designed diagram that clearly illustrates the model architecture. The attention module connections are easy to follow.",
                "caption_review": "Comprehensive caption explaining each component of the architecture.",
                "figrefs_review": "Properly referenced in Section 2 (Methodology) and Section 4 (Discussion).",
                "source_path": None,
            },
        ]

        try:
            self._webhooks.publish_figure_reviews({"reviews": fake_reviews})
            logger.info(
                "[FakeRunner %s] Posted figure_reviews webhook with %d reviews",
                self._run_id[:8],
                len(fake_reviews),
            )
        except Exception:
            logger.exception(
                "[FakeRunner %s] Failed to post figure_reviews webhook", self._run_id[:8]
            )

    def _emit_fake_review(self) -> None:
        """Emit a fake LLM review by storing it in the database and publishing a webhook."""
        summary = "This paper presents a novel approach to the problem with solid experimental validation. The methodology is sound and the results demonstrate clear improvements over baseline approaches."
        strengths = [
            "Novel approach with clear motivation",
            "Comprehensive experimental evaluation",
            "Well-written and easy to follow",
            "Strong empirical results across multiple benchmarks",
        ]
        weaknesses = [
            "Limited comparison with recent state-of-the-art methods",
            "Some experimental details could be clarified",
            "Scalability concerns not fully addressed",
        ]
        questions = [
            "How does the approach scale to larger datasets?",
            "What is the computational overhead compared to baselines?",
        ]
        limitations = [
            "Limited to specific domain",
            "Requires significant computational resources",
        ]
        originality = 3.5
        quality = 3.0
        clarity = 3.5
        significance = 3.0
        soundness = 3.0
        presentation = 3.5
        contribution = 3.0
        overall = 7.0
        confidence = 4.0
        decision = "Accept"
        ethical_concerns = False
        source_path = None
        created_at = datetime.now(timezone.utc)

        # Publish the webhook (server will generate the ID and persist to database)
        webhook_payload = {
            "summary": summary,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "originality": originality,
            "quality": quality,
            "clarity": clarity,
            "significance": significance,
            "questions": questions,
            "limitations": limitations,
            "ethical_concerns": ethical_concerns,
            "soundness": soundness,
            "presentation": presentation,
            "contribution": contribution,
            "overall": overall,
            "confidence": confidence,
            "decision": decision,
            "source_path": source_path,
            "created_at": created_at.isoformat(),
        }

        try:
            self._webhooks.publish_review_completed(webhook_payload)
            logger.info("[FakeRunner %s] Posted review completed webhook", self._run_id[:8])
        except Exception:
            logger.exception(
                "[FakeRunner %s] Failed to post review completed webhook", self._run_id[:8]
            )

    def _publish_fake_artifact(self) -> None:
        temp_dir = Path(os.environ.get("TMPDIR") or "/tmp")
        artifact_path = temp_dir / f"{self._run_id}-fake-result.txt"
        artifact_path.write_text("fake run output\n", encoding="utf-8")
        logger.info("Uploading fake artifact %s", artifact_path)
        publisher = ArtifactPublisher(
            run_id=self._run_id,
            webhook_base_url=self._webhook_url,
            webhook_token=self._webhook_token,
            webhook_client=self._webhook_client,
        )
        spec = ArtifactSpec(
            artifact_type="fake_result",
            path=artifact_path,
            packaging="file",
            archive_name=None,
            exclude_dir_names=tuple(),
        )
        try:
            publisher.publish(spec=spec)
            logger.info("[FakeRunner %s] Artifact published to S3", self._run_id[:8])
        except Exception:
            logger.exception("Failed to publish fake artifact for run %s", self._run_id)
        finally:
            publisher.close()
        try:
            artifact_path.unlink()
        except OSError:
            logger.warning("Failed to delete temp artifact %s", artifact_path)

    def _publish_fake_plot_artifact(self) -> None:
        plot_path = self._data_dir / "loss_curves.png"
        if not plot_path.exists():
            logger.warning("Fake plot not found at %s; skipping plot upload", plot_path)
            return
        logger.info("Uploading fake plot artifact %s", plot_path)
        publisher = ArtifactPublisher(
            run_id=self._run_id,
            webhook_base_url=self._webhook_url,
            webhook_token=self._webhook_token,
            webhook_client=self._webhook_client,
        )
        spec = ArtifactSpec(
            artifact_type="plot",
            path=plot_path,
            packaging="file",
            archive_name=None,
            exclude_dir_names=tuple(),
        )
        try:
            publisher.publish(spec=spec)
            self._plot_filename = plot_path.name
        except Exception:
            logger.exception("Failed to publish fake plot artifact for run %s", self._run_id)
        finally:
            publisher.close()

    def _publish_run_started(self) -> None:
        try:
            if self._webhook_client is not None:
                self._webhook_client.publish_run_started()
        except Exception:  # noqa: BLE001 - fake runner best-effort
            logger.exception("Failed to publish run-started for %s", self._run_id)

    def _publish_run_finished(self, success: bool, message: str) -> None:
        try:
            if self._webhook_client is not None:
                self._webhook_client.publish_run_finished(
                    success=success,
                    message=message,
                )
        except Exception:  # noqa: BLE001 - fake runner best-effort
            logger.exception("Failed to publish run-finished for %s", self._run_id)

    def _store_tree_viz(self, *, stage_number: int, version: int = 1) -> None:
        stage_id = f"Stage_{stage_number}"
        data_path = self._data_dir / f"stage_{stage_number}_tree_data.json"
        if not data_path.exists():
            logger.warning("Fake tree viz data not found for %s at %s", stage_id, data_path)
            return
        logger.info("Storing fake tree viz for %s from %s", stage_id, data_path)
        with data_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        n_nodes = len(payload.get("layout") or payload.get("code") or [])
        if n_nodes > 0:
            # Inject fake Codex task markdown per node (for UI testing).
            codex_task = payload.get("codex_task")
            if not isinstance(codex_task, list) or len(codex_task) != n_nodes:
                codex_task = ["" for _ in range(n_nodes)]
            for idx in range(n_nodes):
                codex_task[idx] = "\n".join(
                    [
                        "# Codex task (fake)",
                        "",
                        f"- stage: {stage_id}",
                        f"- node_index: {idx}",
                        f"- version: {version}",
                        "",
                        "## Instructions",
                        "Write code for this node based on the context.",
                        "",
                        "## Context",
                        "This is synthetic data produced by the fake runner.",
                        "",
                    ]
                )
            payload["codex_task"] = codex_task

        if self._plot_filename:
            if n_nodes > 0:
                plots = payload.get("plots")
                if not isinstance(plots, list) or len(plots) != n_nodes:
                    plots = [[] for _ in range(n_nodes)]
                plots[0] = [self._plot_filename]
                payload["plots"] = plots
                plot_paths = payload.get("plot_paths")
                if not isinstance(plot_paths, list) or len(plot_paths) != n_nodes:
                    plot_paths = [[] for _ in range(n_nodes)]
                plot_paths[0] = [self._plot_filename]
                payload["plot_paths"] = plot_paths
                logger.debug(
                    "Injected plot %s into node 0 plots/plot_paths for %s",
                    self._plot_filename,
                    stage_id,
                )

        # Publish tree_viz_stored event via webhook (server will generate ID and persist to DB)
        try:
            self._webhooks.publish_tree_viz_stored(
                {
                    "stage_id": stage_id,
                    "version": version,
                    "viz": payload,  # Include full viz data in webhook
                }
            )
            logger.info(
                "Posted tree_viz_stored webhook: run=%s stage=%s",
                self._run_id,
                stage_id,
            )
        except Exception:  # noqa: BLE001 - fake runner best-effort
            logger.exception(
                "Failed to post tree_viz_stored webhook for run=%s stage=%s",
                self._run_id,
                stage_id,
            )

    def _emit_fake_best_node(self, *, stage_name: str, stage_index: int) -> None:
        node_id = f"{stage_name}-best-{uuid.uuid4().hex[:8]}"
        reasoning = (
            f"Selected synthetic best node for {stage_name} after stage index {stage_index + 1}."
        )
        try:
            self._persistence.queue.put(
                PersistableEvent(
                    kind="best_node_selection",
                    data={
                        "stage": stage_name,
                        "node_id": node_id,
                        "reasoning": reasoning,
                    },
                )
            )
        except Exception:
            logger.exception("Failed to enqueue fake best node event for stage %s", stage_name)


def main() -> None:
    global _speed_factor

    parser = argparse.ArgumentParser(description="Fake RunPod server for local testing")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speed multiplier for all wait times (e.g., --speed 2 runs 2x faster)",
    )
    args = parser.parse_args()

    if args.speed <= 0:
        parser.error("--speed must be a positive number")

    _speed_factor = args.speed
    if _speed_factor != 1.0:
        logger.info(
            "Running with speed factor %.1fx (wait times reduced to %.0f%%)",
            _speed_factor,
            100 / _speed_factor,
        )

    port_value = _require_env("FAKE_RUNPOD_PORT")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(port_value),
        log_level="debug",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
