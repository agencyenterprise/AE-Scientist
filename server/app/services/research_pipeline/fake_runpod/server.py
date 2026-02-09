"""FastAPI server that mocks the RunPod API."""

import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List

if TYPE_CHECKING:
    from .runner import FakeRunner

from fastapi import Body, FastAPI, HTTPException, Query

from app.services.research_pipeline.runpod.runpod_initialization import WORKSPACE_PATH

# Import runner module to register the runner factory (must happen before create_runner is called)
from . import runner as _runner_module  # noqa: F401
from .models import (
    PodRecord,
    PodRequest,
    SkipStageRequest,
    TelemetryRecord,
    TerminateExecutionRequest,
)
from .state import create_runner, get_executions, get_lock, get_runners, get_speed_factor

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle startup and shutdown gracefully."""
    try:
        yield
    except asyncio.CancelledError:
        pass


# FastAPI app instance
app = FastAPI(title="Fake RunPod Server", lifespan=lifespan)

# Local state (not shared with runner)
_pods: Dict[str, PodRecord] = {}
_telemetry_events: List[TelemetryRecord] = []


# =============================================================================
# Helper functions
# =============================================================================


def _require_env(name: str) -> str:
    """Require an environment variable to be set."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required for fake RunPod server")
    return value


def _extract_bash_c_script(*, docker_start_cmd: List[str]) -> str:
    """Extract the script from a bash -c command."""
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
    """Parse .env file content from dockerStartCmd heredoc."""
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


def _build_pod_response(record: PodRecord) -> Dict[str, Any]:
    """Build a pod response object."""
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
    """Schedule a pod to transition to RUNNING after a delay."""
    _lock = get_lock()
    speed_factor = get_speed_factor()

    def _transition() -> None:
        time.sleep(delay_seconds / speed_factor)
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
    """Start a FakeRunner for a pod."""
    runner = create_runner(
        run_id=record.run_id,
        pod_id=record.id,
        webhook_url=webhook_url,
        webhook_token=webhook_token,
    )
    thread = threading.Thread(target=runner.run, name=f"fake-runner-{record.run_id}", daemon=True)
    thread.start()
    return runner


# =============================================================================
# Pod endpoints
# =============================================================================


@app.post("/pods")
def create_pod(request: PodRequest = Body(...)) -> Dict[str, object]:
    """Create a new pod."""
    _lock = get_lock()
    _runners_by_run_id = get_runners()

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
    """Get a pod by ID."""
    _lock = get_lock()
    with _lock:
        record = _pods.get(pod_id)
    if record is None:
        raise HTTPException(status_code=404, detail="pod not found")
    return _build_pod_response(record)


@app.delete("/pods/{pod_id}")
def delete_pod(pod_id: str) -> Dict[str, str]:
    """Delete a pod."""
    logger.info("Received delete_pod request: pod_id=%s", pod_id)
    return {"status": "deleted"}


# =============================================================================
# Billing and GraphQL endpoints
# =============================================================================


@app.get("/billing/pods")
def get_billing_summary(
    podId: str = Query(...), grouping: str = Query(...)
) -> List[Dict[str, object]]:
    """Get billing summary for a pod."""
    _lock = get_lock()
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
    """Handle GraphQL queries."""
    query = body.get("query")
    variables = body.get("variables", {})
    if "podHostId" in json.dumps(query):
        return {"data": {"pod": {"machine": {"podHostId": "fake-host"}}}}
    return {"data": {}, "variables": variables}


# =============================================================================
# Stage skip and execution termination
# =============================================================================


@app.post("/skip-stage")
def skip_stage(request: SkipStageRequest = Body(...)) -> Dict[str, object]:
    """Request to skip a stage."""
    _lock = get_lock()
    _runners_by_run_id = get_runners()
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
    """Terminate an execution."""
    _lock = get_lock()
    _executions_by_id = get_executions()
    _runners_by_run_id = get_runners()
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


# =============================================================================
# Telemetry endpoints
# =============================================================================


@app.post("/telemetry/run-started", status_code=204)
def telemetry_run_started(payload: Dict[str, object] = Body(...)) -> None:
    """Record run-started telemetry."""
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/run-started", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/run-finished", status_code=204)
def telemetry_run_finished(payload: Dict[str, object] = Body(...)) -> None:
    """Record run-finished telemetry."""
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/run-finished", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/heartbeat", status_code=204)
def telemetry_heartbeat(payload: Dict[str, object] = Body(...)) -> None:
    """Record heartbeat telemetry."""
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/heartbeat", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/hw-stats", status_code=204)
def telemetry_hw_stats(payload: Dict[str, object] = Body(...)) -> None:
    """Record hardware stats telemetry."""
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/hw-stats", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/stage-progress", status_code=204)
def telemetry_stage_progress(payload: Dict[str, object] = Body(...)) -> None:
    """Record stage progress telemetry."""
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/stage-progress", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/stage-completed", status_code=204)
def telemetry_stage_completed(payload: Dict[str, object] = Body(...)) -> None:
    """Record stage completed telemetry."""
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/stage-completed", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/gpu-shortage", status_code=204)
def telemetry_gpu_shortage(payload: Dict[str, object] = Body(...)) -> None:
    """Record GPU shortage telemetry."""
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/gpu-shortage", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/paper-generation-progress", status_code=204)
def telemetry_paper_generation_progress(payload: Dict[str, object] = Body(...)) -> None:
    """Record paper generation progress telemetry."""
    _telemetry_events.append(
        TelemetryRecord(
            path="/telemetry/paper-generation-progress", payload=payload, received_at=time.time()
        )
    )


@app.get("/telemetry")
def list_telemetry() -> List[Dict[str, object]]:
    """List all telemetry events."""
    return [
        {
            "path": record.path,
            "payload": record.payload,
            "received_at": record.received_at,
        }
        for record in _telemetry_events
    ]
