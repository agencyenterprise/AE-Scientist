"""Core FakeRunner class with lifecycle and thread management."""

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

# fmt: off
# isort: off
from research_pipeline.ai_scientist.api_types import (  # type: ignore[import-not-found]
    ExecutionType,
    RunCompletedEventPayload,
    RunLogEvent,
    RunType,
    Status6 as RunCompletedStatus,
)
# isort: on
# fmt: on
from research_pipeline.ai_scientist.telemetry.event_persistence import (  # type: ignore[import-not-found]
    EventPersistenceManager,
    PersistableEvent,
    WebhookClient,
)

from ..local_persistence import LocalPersistence
from ..models import FAKE_INITIALIZATION_STEP_DELAYS_SECONDS
from ..state import get_executions, get_lock, get_speed_factor
from ..webhooks import FakeRunPodWebhookPublisher

logger = logging.getLogger(__name__)


class FakeRunnerCore:
    """Core lifecycle and thread management for FakeRunner."""

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
        self._data_dir = Path(__file__).parent.parent / "data"
        self._plot_filename: str | None = None
        self._random_exec_time_seconds = 12.0
        self._code_event_delay_seconds = 12.0
        self._stage_skip_windows: dict[str, tuple[str, str]] = {}
        self._webhooks = FakeRunPodWebhookPublisher(
            client=self._webhook_client, run_id=self._run_id
        )
        self._stage_skip_requested = threading.Event()
        self._stage_skip_reason: str | None = None
        self._stage_skip_lock = threading.Lock()

    def _get_speed_factor(self) -> float:
        """Get the current speed factor from the state module."""
        return get_speed_factor()

    def _sleep(self, seconds: float) -> None:
        """Sleep for the given duration, adjusted by the global speed factor."""
        adjusted = seconds / self._get_speed_factor()
        time.sleep(adjusted)

    def _adjusted_timeout(self, seconds: float) -> float:
        """Return the timeout adjusted by the global speed factor."""
        return seconds / self._get_speed_factor()

    def request_stage_skip(self, *, reason: str) -> None:
        """Request that the current stage be skipped."""
        with self._stage_skip_lock:
            self._stage_skip_reason = reason
        self._stage_skip_requested.set()

    def _consume_stage_skip_request(self) -> str | None:
        """Consume a pending stage skip request, returning the reason if any."""
        if not self._stage_skip_requested.is_set():
            return None
        self._stage_skip_requested.clear()
        with self._stage_skip_lock:
            reason = self._stage_skip_reason
            self._stage_skip_reason = None
        return reason

    def _wait_or_skip(self, *, timeout_seconds: float) -> str | None:
        """Wait for the given timeout or until a skip is requested."""
        if not self._stage_skip_requested.wait(timeout=self._adjusted_timeout(timeout_seconds)):
            return None
        return self._consume_stage_skip_request()

    def terminate_execution(self, *, execution_id: str, payload: str) -> tuple[int, str]:
        """Terminate an execution, returning (status_code, detail)."""
        _lock = get_lock()
        _executions_by_id = get_executions()

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
            data=RunLogEvent(
                message=f"Termination requested for execution {execution_id}: {payload}",
                level="warn",
            ),
        )
        # Publish termination webhook
        try:
            self._webhooks.publish_run_completed(
                RunCompletedEventPayload(
                    execution_id=execution_id,
                    stage=record.stage,
                    run_type=RunType(record.run_type),
                    execution_type=ExecutionType.stage_goal,  # Default for terminations
                    status=RunCompletedStatus.failed,
                    exec_time=exec_time,
                    completed_at=now.isoformat(),
                    is_seed_node=False,
                    is_seed_agg_node=False,
                    node_index=0,  # Unknown for terminated executions
                )
            )
        except Exception:  # noqa: BLE001 - fake runner best-effort
            logger.exception(
                "Failed to publish terminated execution webhook for %s (stage=%s)",
                execution_id,
                record.stage,
            )
        with _lock:
            latest = _executions_by_id.get(execution_id)
            if latest is not None and latest.run_id == self._run_id:
                _executions_by_id[execution_id] = latest._replace(status="terminated")
        return 200, ""

    def _enqueue_event(self, *, kind: str, data: BaseModel) -> None:
        """Enqueue an event for publishing."""
        try:
            self._persistence.queue.put(PersistableEvent(kind=kind, data=data))
        except Exception:
            logger.exception("Failed to enqueue %s event for run %s", kind, self._run_id)

    def run(self) -> None:
        """Run the fake research pipeline simulation."""
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
        """Simulate the initialization phase."""
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
        """Background loop that sends heartbeats."""
        webhook_client = self._webhook_client
        while not self._heartbeat_stop.is_set():
            logger.debug("Heartbeat tick for run %s", self._run_id)
            self._persistence.queue.put(
                PersistableEvent(
                    kind="run_log", data=RunLogEvent(message="heartbeat", level="debug")
                )
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
        """Background loop that generates periodic log messages."""
        counter = 1
        while not self._log_stop.is_set():
            message = f"[FakeRunner {self._run_id[:8]}] periodic log #{counter}"
            try:
                self._persistence.queue.put(
                    PersistableEvent(
                        kind="run_log", data=RunLogEvent(message=message, level="info")
                    )
                )
            except Exception:
                logger.exception("Failed to enqueue periodic log for run %s", self._run_id)
            counter += 1
            self._log_stop.wait(timeout=self._adjusted_timeout(self._periodic_log_interval_seconds))

    def _publish_run_started(self) -> None:
        """Publish the run-started webhook."""
        try:
            if self._webhook_client is not None:
                self._webhook_client.publish_run_started()
        except Exception:  # noqa: BLE001 - fake runner best-effort
            logger.exception("Failed to publish run-started for %s", self._run_id)

    def _publish_run_finished(self, success: bool, message: str) -> None:
        """Publish the run-finished webhook."""
        try:
            if self._webhook_client is not None:
                self._webhook_client.publish_run_finished(
                    success=success,
                    message=message,
                )
        except Exception:  # noqa: BLE001 - fake runner best-effort
            logger.exception("Failed to publish run-finished for %s", self._run_id)

    # These methods will be provided by mixins
    def _publish_fake_plot_artifact(self) -> None:
        raise NotImplementedError

    def _emit_fake_hw_stats(self) -> None:
        raise NotImplementedError

    def _emit_progress_flow(self) -> None:
        raise NotImplementedError

    def _emit_fake_token_usage(self) -> None:
        raise NotImplementedError

    def _publish_fake_artifact(self) -> None:
        raise NotImplementedError

    def _emit_fake_figure_reviews(self) -> None:
        raise NotImplementedError

    def _emit_fake_review(self) -> None:
        raise NotImplementedError
