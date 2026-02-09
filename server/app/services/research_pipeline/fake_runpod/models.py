"""Data models and constants for the fake RunPod server."""

from datetime import datetime
from typing import Dict, List, NamedTuple

from pydantic import BaseModel

# Timing constants
MIN_FAKE_RUNFILE_RUNNING_SECONDS = 15.0
MIN_FAKE_CODEX_OUTLIVES_RUNFILE_SECONDS = 5.0
FAKE_INITIALIZATION_STEP_DELAYS_SECONDS: list[tuple[str, float]] = [
    ("Cloning repository", 6.0),
    ("Installing OS packages", 8.0),
    ("Installing Python dependencies", 10.0),
    ("Configuring environment", 4.0),
]


class PodRecord(NamedTuple):
    """Record of a fake pod."""

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
    """Request to create a new pod."""

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
    """Request to skip a stage."""

    run_id: str
    reason: str


class BillingRecord(NamedTuple):
    """Billing record for a pod."""

    podId: str
    amount: float
    timeBilledMs: int


class TelemetryRecord(NamedTuple):
    """Record of a telemetry event."""

    path: str
    payload: Dict[str, object]
    received_at: float


class TerminateExecutionRequest(BaseModel):
    """Request to terminate an execution."""

    payload: str


class ExecutionRecord(NamedTuple):
    """Record of a code execution."""

    run_id: str
    stage: str
    run_type: str
    started_at: datetime
    status: str
