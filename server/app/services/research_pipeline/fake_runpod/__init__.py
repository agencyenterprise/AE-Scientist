"""Fake RunPod server for local testing.

This package provides a mock RunPod API server that simulates research pipeline runs
without requiring actual GPU infrastructure.

Usage:
    python -m app.services.research_pipeline.fake_runpod --speed 2
"""

from .__main__ import main
from .models import (
    FAKE_INITIALIZATION_STEP_DELAYS_SECONDS,
    MIN_FAKE_CODEX_OUTLIVES_RUNFILE_SECONDS,
    MIN_FAKE_RUNFILE_RUNNING_SECONDS,
    BillingRecord,
    ExecutionRecord,
    PodRecord,
    PodRequest,
    SkipStageRequest,
    TelemetryRecord,
    TerminateExecutionRequest,
)
from .runner import FakeRunner
from .server import app
from .state import get_speed_factor, set_speed_factor
from .webhooks import FakeRunPodWebhookPublisher

__all__ = [
    # Entry point
    "main",
    # FastAPI app
    "app",
    "get_speed_factor",
    "set_speed_factor",
    # Runner
    "FakeRunner",
    # Webhook publisher
    "FakeRunPodWebhookPublisher",
    # Models
    "BillingRecord",
    "ExecutionRecord",
    "FAKE_INITIALIZATION_STEP_DELAYS_SECONDS",
    "MIN_FAKE_CODEX_OUTLIVES_RUNFILE_SECONDS",
    "MIN_FAKE_RUNFILE_RUNNING_SECONDS",
    "PodRecord",
    "PodRequest",
    "SkipStageRequest",
    "TelemetryRecord",
    "TerminateExecutionRequest",
]
