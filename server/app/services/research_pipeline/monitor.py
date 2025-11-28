import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.services import get_database
from app.services.database import DatabaseManager
from app.services.database.research_pipeline_runs import ResearchPipelineRun
from app.services.research_pipeline import RunPodError, terminate_pod
from app.services.research_pipeline.runpod_launcher import RunPodCreator

logger = logging.getLogger(__name__)


class ResearchPipelineMonitor:
    def __init__(
        self,
        *,
        poll_interval_seconds: int,
        heartbeat_timeout_seconds: int,
        max_missed_heartbeats: int,
        startup_grace_seconds: int,
    ) -> None:
        self._poll_interval = poll_interval_seconds
        self._heartbeat_timeout = timedelta(seconds=heartbeat_timeout_seconds)
        self._max_missed_heartbeats = max_missed_heartbeats
        self._startup_grace = timedelta(seconds=startup_grace_seconds)
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        api_key = os.environ.get("RUNPOD_API_KEY")
        self._runpod_creator: Optional[RunPodCreator] = (
            RunPodCreator(api_key=api_key) if api_key else None
        )

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        logger.info("Research pipeline monitor started.")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None
        logger.info("Research pipeline monitor stopped.")

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_runs()
            except Exception:
                logger.exception("Pipeline monitor encountered an error.")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval)
            except asyncio.TimeoutError:
                continue

    def _check_runs(self) -> None:
        db = get_database()
        runs = db.list_active_research_pipeline_runs()
        if not runs:
            return
        now = datetime.now(timezone.utc)
        for run in runs:
            if run.status == "pending":
                self._handle_pending_run(db, run, now)
            elif run.status == "running":
                self._handle_running_run(db, run, now)

    def _handle_pending_run(
        self, db: "DatabaseManager", run: ResearchPipelineRun, now: datetime
    ) -> None:
        deadline = run.start_deadline_at or (run.created_at + self._startup_grace)
        if deadline and now > deadline:
            self._fail_run(db, run, "Pipeline did not start within the grace period.")

    def _handle_running_run(
        self, db: "DatabaseManager", run: ResearchPipelineRun, now: datetime
    ) -> None:
        if run.last_heartbeat_at is None:
            deadline = run.start_deadline_at or (run.created_at + self._startup_grace)
            if deadline and now > deadline:
                self._fail_run(db, run, "Pipeline failed to send an initial heartbeat.")
            return

        delta = now - run.last_heartbeat_at
        if delta > self._heartbeat_timeout:
            failures = run.heartbeat_failures + 1
            db.update_research_pipeline_run(run_id=run.run_id, heartbeat_failures=failures)
            if failures >= self._max_missed_heartbeats:
                self._fail_run(db, run, "Pipeline heartbeats exceeded failure threshold.")
            return

        if run.heartbeat_failures > 0:
            db.update_research_pipeline_run(run_id=run.run_id, heartbeat_failures=0)

        if run.pod_id and self._runpod_creator is not None:
            try:
                pod = self._runpod_creator.get_pod(run.pod_id)
                status = pod.get("desiredStatus")
                if status not in ("RUNNING", "PENDING"):
                    self._fail_run(db, run, f"Pod status is {status}; terminating run.")
            except RunPodError as exc:
                logger.warning("Failed to poll RunPod status for %s: %s", run.pod_id, exc)

    def _fail_run(self, db: "DatabaseManager", run: ResearchPipelineRun, message: str) -> None:
        logger.warning("Marking run %s as failed: %s", run.run_id, message)
        db.update_research_pipeline_run(
            run_id=run.run_id,
            status="failed",
            error_message=message,
        )
        if run.pod_id:
            try:
                terminate_pod(pod_id=run.pod_id)
            except RuntimeError as exc:
                logger.warning("Failed to terminate pod %s: %s", run.pod_id, exc)


DEFAULT_POLL_INTERVAL_SECONDS = 60
DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_MISSED_HEARTBEATS = 5
DEFAULT_STARTUP_GRACE_SECONDS = 300

pipeline_monitor = ResearchPipelineMonitor(
    poll_interval_seconds=DEFAULT_POLL_INTERVAL_SECONDS,
    heartbeat_timeout_seconds=DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    max_missed_heartbeats=DEFAULT_MAX_MISSED_HEARTBEATS,
    startup_grace_seconds=DEFAULT_STARTUP_GRACE_SECONDS,
)
