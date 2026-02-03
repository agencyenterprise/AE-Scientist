import asyncio
import logging
import os
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Protocol, cast

from psycopg import AsyncConnection

from app.api.research_pipeline_runs import _generate_run_webhook_token
from app.api.research_pipeline_stream import publish_stream_event
from app.config import settings
from app.models import ResearchRunEvent
from app.models.sse import ResearchRunRunEvent as SSERunEvent
from app.services import get_database
from app.services.database import DatabaseManager
from app.services.database.billing import CreditTransaction
from app.services.database.research_pipeline_run_termination import ResearchPipelineRunTermination
from app.services.database.research_pipeline_runs import PodUpdateInfo, ResearchPipelineRun
from app.services.narrator.narrator_service import ingest_narration_event
from app.services.research_pipeline.billing_retry_worker import BillingRetryWorker
from app.services.research_pipeline.pod_restart import attempt_pod_restart
from app.services.research_pipeline.pod_termination_worker import (
    PodTerminationWorker,
    notify_termination_requested,
    publish_termination_status_event,
)
from app.services.research_pipeline.runpod import (
    RunPodError,
    RunPodManager,
    get_supported_gpu_types,
)


class ResearchRunStore(Protocol):
    async def list_active_research_pipeline_runs(self) -> list[ResearchPipelineRun]: ...
    async def get_research_pipeline_run(self, run_id: str) -> Optional[ResearchPipelineRun]: ...

    async def update_research_pipeline_run(
        self,
        *,
        run_id: str,
        status: Optional[str] = None,
        pod_update_info: Optional[PodUpdateInfo] = None,
        error_message: Optional[str] = None,
        last_heartbeat_at: Optional[datetime] = None,
        heartbeat_failures: Optional[int] = None,
        start_deadline_at: Optional[datetime] = None,
        last_billed_at: Optional[datetime] = None,
        started_running_at: Optional[datetime] = None,
    ) -> None: ...

    async def insert_research_pipeline_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        metadata: Dict[str, object],
        occurred_at: datetime,
    ) -> None: ...

    async def enqueue_research_pipeline_run_termination(
        self,
        *,
        run_id: str,
        trigger: str,
    ) -> ResearchPipelineRunTermination: ...

    async def get_run_owner_user_id(self, run_id: str) -> Optional[int]: ...

    async def get_user_wallet_balance(self, user_id: int) -> int: ...

    async def add_completed_transaction(
        self,
        *,
        user_id: int,
        amount: int,
        transaction_type: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
        stripe_session_id: Optional[str] = None,
    ) -> CreditTransaction: ...


logger = logging.getLogger(__name__)

_PIPELINE_MONITOR_ADVISORY_LOCK_KEY_1 = 184467
_PIPELINE_MONITOR_ADVISORY_LOCK_KEY_2 = 991733

_TERMINATION_LEASE_SECONDS = 50 * 60
_TERMINATION_STUCK_SECONDS = 60 * 60
_TERMINATION_MAX_CONCURRENCY = 8


class PipelineMonitorError(Exception):
    """Raised when the pipeline monitor encounters an unexpected error."""


class ResearchPipelineMonitor:
    def __init__(
        self,
        *,
        poll_interval_seconds: int,
        heartbeat_timeout_seconds: int,
        max_missed_heartbeats: int,
        startup_grace_seconds: int,
        max_runtime_hours: int,
    ) -> None:
        self._poll_interval = poll_interval_seconds
        self._heartbeat_timeout = timedelta(seconds=heartbeat_timeout_seconds)
        self._max_missed_heartbeats = max_missed_heartbeats
        self._startup_grace = timedelta(seconds=startup_grace_seconds)
        self._max_runtime = timedelta(hours=max_runtime_hours)
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._runpod_manager: RunPodManager = RunPodManager(api_key=settings.runpod.api_key)

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="PipelineMonitor")
        logger.debug("Research pipeline monitor task started (pid=%s).", os.getpid())

    async def stop(self) -> None:
        if self._task is None:
            return
        if self._stop_event is not None:
            self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=self._poll_interval + 1)
        except asyncio.TimeoutError:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        finally:
            self._task = None
            self._stop_event = None
        logger.debug("Research pipeline monitor task stopped (pid=%s).", os.getpid())

    async def _run(self) -> None:
        stop_event = self._stop_event
        if stop_event is None:
            stop_event = asyncio.Event()
            self._stop_event = stop_event
        while not stop_event.is_set():
            is_leader = await self._try_run_as_leader(stop_event=stop_event)
            if is_leader:
                continue
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._poll_interval)
            except asyncio.TimeoutError:
                continue

    async def _try_run_as_leader(self, *, stop_event: asyncio.Event) -> bool:
        db = get_database()
        async with db.aget_connection() as conn:
            lock_acquired = await self._try_acquire_global_monitor_lock(conn=conn)
            if not lock_acquired:
                return False

            logger.info("Pipeline monitor elected leader (pid=%s).", os.getpid())
            termination_task: asyncio.Task[None] | None = None
            billing_retry_task: asyncio.Task[None] | None = None
            try:
                termination_task = asyncio.create_task(
                    PodTerminationWorker(
                        runpod_manager=self._runpod_manager,
                        max_concurrency=_TERMINATION_MAX_CONCURRENCY,
                        poll_interval_seconds=self._poll_interval,
                    ).run(stop_event=stop_event),
                    name="PodTerminationDispatcher",
                )
                billing_retry_task = asyncio.create_task(
                    BillingRetryWorker(db=db).run(stop_event=stop_event),
                    name="BillingRetryWorker",
                )
                while not stop_event.is_set():
                    try:
                        await self._check_runs()
                    except PipelineMonitorError:
                        logger.exception("Pipeline monitor encountered an error.")
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=self._poll_interval)
                    except asyncio.TimeoutError:
                        continue
            finally:
                if termination_task is not None:
                    termination_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await termination_task
                if billing_retry_task is not None:
                    billing_retry_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await billing_retry_task
                await self._release_global_monitor_lock(conn=conn)
                logger.info("Pipeline monitor relinquished leadership (pid=%s).", os.getpid())
            return True

    async def _try_acquire_global_monitor_lock(self, *, conn: AsyncConnection[object]) -> bool:
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT pg_try_advisory_lock(%s, %s)",
                    (
                        _PIPELINE_MONITOR_ADVISORY_LOCK_KEY_1,
                        _PIPELINE_MONITOR_ADVISORY_LOCK_KEY_2,
                    ),
                )
                row = cast("tuple[object, ...] | None", await cursor.fetchone())
                if row is None:
                    return False
                return bool(row[0])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to acquire pipeline monitor leader lock: %s", exc)
            return False

    async def _release_global_monitor_lock(self, *, conn: AsyncConnection[object]) -> None:
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT pg_advisory_unlock(%s, %s)",
                    (
                        _PIPELINE_MONITOR_ADVISORY_LOCK_KEY_1,
                        _PIPELINE_MONITOR_ADVISORY_LOCK_KEY_2,
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to release pipeline monitor leader lock: %s", exc)

    async def _check_runs(self) -> None:
        try:
            db = cast("ResearchRunStore", get_database())
            runs = await db.list_active_research_pipeline_runs()
            if not runs:
                logger.debug("Pipeline monitor heartbeat: no active runs.")
                return
            logger.info(
                "Pipeline monitor inspecting %s active runs: %s",
                len(runs),
                [f"{run.run_id}:{run.status}" for run in runs],
            )
            now = datetime.now(timezone.utc)
            for run in runs:
                if run.status == "pending":
                    await self._handle_pending_run(db, run, now)
                elif run.status == "initializing":
                    await self._handle_pending_run(db, run, now)
                elif run.status == "running":
                    await self._handle_running_run(db, run, now)
        except Exception as exc:  # noqa: BLE001
            raise PipelineMonitorError from exc

    async def _handle_pending_run(
        self, db: "ResearchRunStore", run: ResearchPipelineRun, now: datetime
    ) -> None:
        deadline = run.start_deadline_at
        if deadline is None:
            logger.info(
                "Run %s pending; launch has not scheduled a deadline yet.",
                run.run_id,
            )
            return
        if deadline:
            remaining = (deadline - now).total_seconds()
            if remaining > 0:
                logger.info(
                    "Run %s pending; waiting for pod start (%.0fs remaining).",
                    run.run_id,
                    remaining,
                )
        if deadline and now > deadline:
            # Try restart instead of immediate failure
            actual_db = get_database()
            webhook_token, webhook_token_hash = _generate_run_webhook_token()
            gpu_types = [run.gpu_type] if run.gpu_type else get_supported_gpu_types()
            restarted = await attempt_pod_restart(
                db=actual_db,
                run=run,
                reason="startup_timeout",
                gpu_types=gpu_types,
                webhook_token=webhook_token,
                webhook_token_hash=webhook_token_hash,
            )
            if not restarted:
                # Max restarts exceeded, fail permanently
                await self._fail_run(
                    db,
                    run,
                    f"Pipeline did not start within the grace period after {run.restart_count} restart attempt(s).",
                    "deadline_exceeded",
                )

    async def _handle_running_run(
        self, db: "ResearchRunStore", run: ResearchPipelineRun, now: datetime
    ) -> None:
        runtime = now - run.created_at
        if runtime > self._max_runtime:
            await self._fail_run(
                db,
                run,
                f"Pipeline exceeded maximum runtime of {self._max_runtime.total_seconds() / 3600:.1f} hours.",
                "deadline_exceeded",
            )
            return

        await self._maybe_backfill_ssh_info(db=db, run=run, now=now)

        if run.last_heartbeat_at is None:
            deadline = run.start_deadline_at
            if deadline is None:
                logger.info(
                    "Run %s awaiting pod start; deadline not scheduled yet.",
                    run.run_id,
                )
                return
            if deadline:
                remaining = (deadline - now).total_seconds()
                logger.info(
                    "Run %s awaiting first heartbeat (%.0fs remaining).",
                    run.run_id,
                    max(0, remaining),
                )
            if deadline and now > deadline:
                await self._fail_run(
                    db,
                    run,
                    "Pipeline failed to send an initial heartbeat.",
                    "heartbeat_timeout",
                )
            return

        delta = now - run.last_heartbeat_at
        if delta > self._heartbeat_timeout:
            failures = run.heartbeat_failures + 1
            await db.update_research_pipeline_run(run_id=run.run_id, heartbeat_failures=failures)
            logger.warning(
                "Run %s missed heartbeat (delta %.0fs). Failure count %s/%s.",
                run.run_id,
                delta.total_seconds(),
                failures,
                self._max_missed_heartbeats,
            )
            if failures >= self._max_missed_heartbeats:
                # Try restart instead of immediate failure
                actual_db = get_database()
                webhook_token, webhook_token_hash = _generate_run_webhook_token()
                gpu_types = [run.gpu_type] if run.gpu_type else get_supported_gpu_types()
                restarted = await attempt_pod_restart(
                    db=actual_db,
                    run=run,
                    reason="heartbeat_timeout",
                    gpu_types=gpu_types,
                    webhook_token=webhook_token,
                    webhook_token_hash=webhook_token_hash,
                )
                if not restarted:
                    # Max restarts exceeded, fail permanently
                    await self._fail_run(
                        db,
                        run,
                        f"Pipeline heartbeats exceeded failure threshold after {run.restart_count} restart attempt(s).",
                        "heartbeat_timeout",
                    )
            return

        if run.heartbeat_failures > 0:
            await db.update_research_pipeline_run(run_id=run.run_id, heartbeat_failures=0)

        if run.pod_id:
            try:
                pod = await self._runpod_manager.get_pod(run.pod_id)
                status = pod.get("desiredStatus")
                if status == "PENDING":
                    logger.info(
                        "Run %s pod %s still pending startup; waiting for readiness.",
                        run.run_id,
                        run.pod_id,
                    )
                elif status not in ("RUNNING", "PENDING"):
                    logger.warning(
                        "Run %s pod %s returned unexpected status '%s'; attempting restart.",
                        run.run_id,
                        run.pod_id,
                        status,
                    )
                    # Try restart instead of immediate failure
                    actual_db = get_database()
                    webhook_token, webhook_token_hash = _generate_run_webhook_token()
                    gpu_types = [run.gpu_type] if run.gpu_type else get_supported_gpu_types()
                    restarted = await attempt_pod_restart(
                        db=actual_db,
                        run=run,
                        reason="container_died",
                        gpu_types=gpu_types,
                        webhook_token=webhook_token,
                        webhook_token_hash=webhook_token_hash,
                    )
                    if not restarted:
                        # Max restarts exceeded, fail permanently
                        await self._fail_run(
                            db,
                            run,
                            f"Pod status is {status} after {run.restart_count} restart attempt(s).",
                            "container_died",
                        )
            except RunPodError as exc:
                logger.warning("Failed to poll RunPod status for %s: %s", run.pod_id, exc)

        await self._bill_run_if_needed(db, run, now)

    async def _fail_run(
        self,
        db: "ResearchRunStore",
        run: ResearchPipelineRun,
        message: str,
        reason: str,
    ) -> None:
        logger.warning("Marking run %s as failed: %s", run.run_id, message)
        now = datetime.now(timezone.utc)
        await db.update_research_pipeline_run(
            run_id=run.run_id,
            status="failed",
            error_message=message,
        )
        await db.insert_research_pipeline_run_event(
            run_id=run.run_id,
            event_type="status_changed",
            metadata={
                "from_status": run.status,
                "to_status": "failed",
                "reason": reason,
                "error_message": message,
            },
            occurred_at=now,
        )
        run_event = ResearchRunEvent(
            id=int(now.timestamp() * 1000),
            run_id=run.run_id,
            event_type="status_changed",
            metadata={
                "from_status": run.status,
                "to_status": "failed",
                "reason": reason,
                "error_message": message,
            },
            occurred_at=now.isoformat(),
        )
        publish_stream_event(
            run.run_id,
            SSERunEvent(
                type="run_event",
                data=run_event,
            ),
        )

        await ingest_narration_event(
            cast(DatabaseManager, db),
            run_id=run.run_id,
            event_type="run_finished",
            event_data={
                "success": False,
                "status": "failed",
                "message": message,
                "reason": reason,
            },
        )

        termination = await db.enqueue_research_pipeline_run_termination(
            run_id=run.run_id,
            trigger=f"pipeline_monitor_failure:{reason}",
        )
        publish_termination_status_event(run_id=run.run_id, termination=termination)
        notify_termination_requested()

    async def _bill_run_if_needed(
        self, db: "ResearchRunStore", run: ResearchPipelineRun, now: datetime
    ) -> None:
        """Create periodic "hold" transactions for estimated GPU cost.

        These holds will be reversed and replaced with the actual cost when the
        pod terminates and we receive the final billing summary from RunPod.
        """
        # Convert run.cost (USD per hour) to cents
        # run.cost is the hourly GPU cost in USD from RunPod
        cost_per_hour_cents = int(run.cost * 100) if run.cost > 0 else 0
        if cost_per_hour_cents <= 0:
            return

        last_billed = run.last_billed_at or run.created_at
        elapsed_seconds = (now - last_billed).total_seconds()
        # Only bill if at least 1 minute has passed
        if elapsed_seconds < 60:
            return

        user_id = await db.get_run_owner_user_id(run.run_id)
        if user_id is None:
            logger.warning("Unable to determine owner for run %s; skipping billing.", run.run_id)
            return

        # Calculate estimated cost based on elapsed time and hourly rate
        estimated_cost_cents = int((cost_per_hour_cents * elapsed_seconds) / 3600)
        if estimated_cost_cents <= 0:
            return

        # Create "hold" transaction (will be reversed at pod termination)
        # Don't check balance or terminate - let run continue regardless
        await db.add_completed_transaction(
            user_id=user_id,
            amount=-estimated_cost_cents,
            transaction_type="hold",
            description=f"Research run {run.run_id} GPU hold ({int(elapsed_seconds)}s)",
            metadata={
                "run_id": run.run_id,
                "hold": True,
                "estimated": True,
                "seconds_billed": int(elapsed_seconds),
                "cost_per_hour_cents": cost_per_hour_cents,
            },
        )

        available = await db.get_user_wallet_balance(user_id)
        await db.insert_research_pipeline_run_event(
            run_id=run.run_id,
            event_type="billing_hold",
            metadata={
                "seconds_billed": int(elapsed_seconds),
                "cost_per_hour_cents": cost_per_hour_cents,
                "hold_amount_cents": estimated_cost_cents,
                "balance_cents": available,
            },
            occurred_at=now,
        )
        await db.update_research_pipeline_run(
            run_id=run.run_id,
            last_billed_at=now,
        )

    async def _maybe_backfill_ssh_info(
        self,
        db: "ResearchRunStore",
        run: ResearchPipelineRun,
        now: datetime,
    ) -> None:
        if (
            not run.pod_id
            or (run.public_ip and run.ssh_port)
            or not self._has_grace_period_elapsed(run=run, now=now)
        ):
            return
        await self._refresh_pod_connection_info(db=db, run=run)

    def _has_grace_period_elapsed(self, *, run: ResearchPipelineRun, now: datetime) -> bool:
        deadline = run.start_deadline_at
        if deadline is None and run.started_running_at is not None:
            deadline = run.started_running_at + self._startup_grace
        if deadline is None:
            return False
        return now >= deadline

    async def _refresh_pod_connection_info(
        self,
        *,
        db: "ResearchRunStore",
        run: ResearchPipelineRun,
    ) -> None:
        assert run.pod_id  # mypy appeasement
        logger.info(
            "Backfilling SSH info for run %s (pod_id=%s) after grace period.",
            run.run_id,
            run.pod_id,
        )
        try:
            pod = await self._runpod_manager.get_pod(run.pod_id)
        except RunPodError as exc:
            logger.warning(
                "Failed to refresh pod %s info for run %s: %s", run.pod_id, run.run_id, exc
            )
            return

        public_ip = pod.get("publicIp")
        port_mappings = pod.get("portMappings") or {}
        ssh_port_value = None
        if isinstance(port_mappings, dict):
            ssh_port_value = port_mappings.get("22")
        if not public_ip or ssh_port_value is None:
            logger.warning(
                "Pod %s still missing SSH data (ip=%s, port=%s); will retry later.",
                run.pod_id,
                public_ip,
                ssh_port_value,
            )
            return
        ssh_port = str(ssh_port_value)

        pod_host_id = run.pod_host_id
        if not pod_host_id:
            pod_host_id = await self._runpod_manager.get_pod_host_id(run.pod_id)

        pod_name = run.pod_name or pod.get("name") or run.pod_id
        machine = pod.get("machine") or {}
        gpu_type = run.gpu_type or machine.get("gpuTypeId") or "unknown"

        await db.update_research_pipeline_run(
            run_id=run.run_id,
            pod_update_info=PodUpdateInfo(
                pod_id=run.pod_id,
                pod_name=str(pod_name),
                gpu_type=str(gpu_type),
                cost=run.cost,
                public_ip=str(public_ip),
                ssh_port=ssh_port,
                pod_host_id=pod_host_id,
            ),
        )
        await db.insert_research_pipeline_run_event(
            run_id=run.run_id,
            event_type="pod_info_backfilled",
            metadata={
                "pod_id": run.pod_id,
                "public_ip": public_ip,
                "ssh_port": ssh_port,
                "pod_host_id": pod_host_id,
            },
            occurred_at=datetime.now(timezone.utc),
        )
        logger.info(
            "Backfilled SSH info for run %s: ip=%s port=%s host=%s",
            run.run_id,
            public_ip,
            ssh_port,
            pod_host_id,
        )


pipeline_monitor = ResearchPipelineMonitor(
    poll_interval_seconds=settings.research_pipeline.monitor_poll_interval_seconds,
    heartbeat_timeout_seconds=settings.research_pipeline.monitor_heartbeat_timeout_seconds,
    max_missed_heartbeats=settings.research_pipeline.monitor_max_missed_heartbeats,
    startup_grace_seconds=settings.research_pipeline.monitor_startup_grace_seconds,
    max_runtime_hours=settings.research_pipeline.monitor_max_runtime_hours,
)
