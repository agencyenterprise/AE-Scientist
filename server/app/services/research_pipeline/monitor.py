import asyncio
import logging
import os
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Dict, Literal, Optional, Protocol, cast

import sentry_sdk
from psycopg import AsyncConnection

from app.api.research_pipeline_events import ingest_narration_event
from app.api.research_pipeline_stream import publish_stream_event
from app.config import settings
from app.models import ResearchRunEvent
from app.models.sse import ResearchRunCompleteData
from app.models.sse import ResearchRunCompleteEvent as SSECompleteEvent
from app.models.sse import ResearchRunRunEvent as SSERunEvent
from app.services import get_database
from app.services.database import DatabaseManager
from app.services.database.billing import CreditTransaction
from app.services.database.research_pipeline_runs import (
    PodUpdateInfo,
    ResearchPipelineRun,
    ResearchPipelineRunTermination,
)
from app.services.research_pipeline import RunPodError, upload_runpod_artifacts_via_ssh
from app.services.research_pipeline.runpod_manager import RunPodManager
from app.services.research_pipeline.termination_workflow import publish_termination_status_event


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

    async def claim_research_pipeline_run_termination(
        self,
        *,
        lease_owner: str,
        lease_seconds: int,
        stuck_seconds: int,
    ) -> ResearchPipelineRunTermination | None: ...

    async def get_research_pipeline_run_termination(
        self,
        *,
        run_id: str,
    ) -> ResearchPipelineRunTermination | None: ...

    async def reschedule_research_pipeline_run_termination(
        self,
        *,
        run_id: str,
        attempts: int,
        error: str,
    ) -> None: ...

    async def mark_research_pipeline_run_termination_artifacts_uploaded(
        self,
        *,
        run_id: str,
    ) -> None: ...

    async def mark_research_pipeline_run_termination_pod_terminated(
        self,
        *,
        run_id: str,
    ) -> None: ...

    async def mark_research_pipeline_run_termination_terminated(
        self,
        *,
        run_id: str,
        attempts: int,
    ) -> None: ...

    async def mark_research_pipeline_run_termination_failed(
        self,
        *,
        run_id: str,
        attempts: int,
        error: str,
    ) -> None: ...

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

_TERMINATION_MAX_UPLOAD_ATTEMPTS = 3
_TERMINATION_LEASE_SECONDS = 50 * 60
_TERMINATION_STUCK_SECONDS = 60 * 60


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
        api_key = os.environ.get("RUNPOD_API_KEY")
        if not api_key:
            raise RuntimeError("RUNPOD_API_KEY environment variable is required.")
        self._runpod_manager: RunPodManager = RunPodManager(api_key=api_key)

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
            try:
                termination_task = asyncio.create_task(
                    self._run_termination_worker(stop_event=stop_event),
                    name="PipelineTerminationWorker",
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
            await self._fail_run(
                db,
                run,
                "Pipeline did not start within the grace period.",
                "pipeline_monitor",
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
                "pipeline_monitor",
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
                    "pipeline_monitor",
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
                await self._fail_run(
                    db,
                    run,
                    "Pipeline heartbeats exceeded failure threshold.",
                    "pipeline_monitor",
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
                        "Run %s pod %s returned unexpected status '%s'; failing run.",
                        run.run_id,
                        run.pod_id,
                        status,
                    )
                    await self._fail_run(
                        db,
                        run,
                        f"Pod status is {status}; terminating run.",
                        "pipeline_monitor",
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

    async def _bill_run_if_needed(
        self, db: "ResearchRunStore", run: ResearchPipelineRun, now: datetime
    ) -> None:
        rate = max(0, settings.RESEARCH_RUN_CREDITS_PER_MINUTE)
        if rate == 0:
            return

        last_billed = run.last_billed_at or run.created_at
        elapsed_minutes = int((now - last_billed).total_seconds() // 60)
        if elapsed_minutes <= 0:
            return

        user_id = await db.get_run_owner_user_id(run.run_id)
        if user_id is None:
            logger.warning("Unable to determine owner for run %s; skipping billing.", run.run_id)
            return

        available = await db.get_user_wallet_balance(user_id)
        if available < rate:
            await self._fail_run(
                db,
                run,
                "Insufficient credits to continue research run.",
                "insufficient_credits",
            )
            return

        billable_minutes = min(elapsed_minutes, available // rate)
        if billable_minutes <= 0:
            await self._fail_run(
                db,
                run,
                "Insufficient credits to continue research run.",
                "insufficient_credits",
            )
            return

        charge_amount = billable_minutes * rate
        await db.add_completed_transaction(
            user_id=user_id,
            amount=-charge_amount,
            transaction_type="debit",
            description=f"Research run {run.run_id} ({billable_minutes} minute(s))",
            metadata={"run_id": run.run_id, "minutes_billed": billable_minutes},
        )
        new_balance = available - charge_amount
        await db.insert_research_pipeline_run_event(
            run_id=run.run_id,
            event_type="billing_debit",
            metadata={
                "minutes_billed": billable_minutes,
                "rate_per_minute": rate,
                "amount_charged": charge_amount,
                "balance": new_balance,
            },
            occurred_at=now,
        )
        await db.update_research_pipeline_run(
            run_id=run.run_id,
            last_billed_at=last_billed + timedelta(minutes=billable_minutes),
        )

        if billable_minutes < elapsed_minutes:
            await self._fail_run(
                db,
                run,
                "Credits exhausted during research run.",
                "insufficient_credits",
            )

    async def _record_pod_billing_event(
        self,
        db: "ResearchRunStore",
        *,
        run_id: str,
        pod_id: str,
        context: str,
    ) -> None:
        try:
            summary = await self._runpod_manager.get_pod_billing_summary(pod_id=pod_id)
        except RunPodError as exc:
            logger.warning("Failed to fetch billing summary for pod %s: %s", pod_id, exc)
            return
        if summary is None:
            return
        metadata = summary._asdict()
        metadata["records"] = [record._asdict() for record in summary.records]
        metadata["context"] = context
        await db.insert_research_pipeline_run_event(
            run_id=run_id,
            event_type="pod_billing_summary",
            metadata=metadata,
            occurred_at=datetime.now(timezone.utc),
        )

    async def _upload_pod_artifacts(self, run: ResearchPipelineRun, *, reason: str) -> None:
        if not run.public_ip or not run.ssh_port:
            logger.info(
                "Run %s missing SSH info; skipping pod artifacts upload (trigger=%s).",
                run.run_id,
                reason,
            )
            return
        try:
            logger.info(
                "Uploading pod artifacts for run %s (trigger=%s, host=%s, port=%s).",
                run.run_id,
                reason,
                run.public_ip,
                run.ssh_port,
            )
            await upload_runpod_artifacts_via_ssh(
                host=run.public_ip,
                port=run.ssh_port,
                run_id=run.run_id,
                trigger=f"pipeline_monitor_failure:{reason}",
            )
        except (RuntimeError, OSError) as exc:
            logger.exception("Failed to upload pod log via SSH for run %s: %s", run.run_id, exc)

    async def _run_termination_worker(self, *, stop_event: asyncio.Event) -> None:
        lease_owner = f"pipeline_monitor:{os.getpid()}"
        logger.info(
            "Termination worker started (lease_owner=%s lease_seconds=%s stuck_seconds=%s max_attempts=%s).",
            lease_owner,
            _TERMINATION_LEASE_SECONDS,
            _TERMINATION_STUCK_SECONDS,
            _TERMINATION_MAX_UPLOAD_ATTEMPTS,
        )
        while not stop_event.is_set():
            db = cast("ResearchRunStore", get_database())
            termination = await db.claim_research_pipeline_run_termination(
                lease_owner=lease_owner,
                lease_seconds=_TERMINATION_LEASE_SECONDS,
                stuck_seconds=_TERMINATION_STUCK_SECONDS,
            )
            if termination is None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self._poll_interval)
                except asyncio.TimeoutError:
                    continue
                continue

            logger.info(
                "Claimed termination work (run_id=%s status=%s attempts=%s artifacts_uploaded=%s pod_terminated=%s).",
                termination.run_id,
                termination.status,
                termination.attempts,
                bool(termination.artifacts_uploaded_at),
                bool(termination.pod_terminated_at),
            )
            await self._process_termination(db=db, termination=termination)

    async def _process_termination(
        self,
        *,
        db: "ResearchRunStore",
        termination: ResearchPipelineRunTermination,
    ) -> None:
        run_id = termination.run_id
        logger.info(
            "Processing termination (run_id=%s status=%s attempts=%s).",
            run_id,
            termination.status,
            termination.attempts,
        )
        run = await db.get_research_pipeline_run(run_id)
        if run is None:
            logger.warning(
                "Termination refers to missing run; marking failed (run_id=%s).",
                run_id,
            )
            await db.mark_research_pipeline_run_termination_failed(
                run_id=run_id,
                attempts=termination.attempts,
                error=f"Run {run_id} not found while processing termination.",
            )
            updated = await db.get_research_pipeline_run_termination(run_id=run_id)
            publish_termination_status_event(run_id=run_id, termination=updated)
            return

        attempt_number = int(termination.attempts or 0) + 1
        logger.info(
            "Termination attempt %s/%s (run_id=%s pod_id=%s).",
            attempt_number,
            _TERMINATION_MAX_UPLOAD_ATTEMPTS,
            run_id,
            run.pod_id,
        )

        # Step A: best-effort artifact upload (skip if already succeeded).
        upload_failed_error: str | None = None
        if (
            termination.artifacts_uploaded_at is None
            and attempt_number <= _TERMINATION_MAX_UPLOAD_ATTEMPTS
        ):
            if run.public_ip and run.ssh_port:
                try:
                    logger.info(
                        "Uploading artifacts via SSH (run_id=%s host=%s port=%s attempt=%s/%s).",
                        run_id,
                        run.public_ip,
                        run.ssh_port,
                        attempt_number,
                        _TERMINATION_MAX_UPLOAD_ATTEMPTS,
                    )
                    await upload_runpod_artifacts_via_ssh(
                        host=run.public_ip,
                        port=run.ssh_port,
                        run_id=run_id,
                        trigger="termination_worker",
                    )
                    await db.mark_research_pipeline_run_termination_artifacts_uploaded(
                        run_id=run_id
                    )
                    logger.info("Artifacts upload succeeded (run_id=%s).", run_id)
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "Artifacts upload failed (run_id=%s attempt=%s/%s).",
                        run_id,
                        attempt_number,
                        _TERMINATION_MAX_UPLOAD_ATTEMPTS,
                    )
                    upload_failed_error = f"Artifact upload failed for run {run_id}: {exc}"
            else:
                upload_failed_error = f"Artifact upload skipped for run {run_id}: missing SSH info."
                logger.warning("%s", upload_failed_error)

            if (
                upload_failed_error is not None
                and attempt_number < _TERMINATION_MAX_UPLOAD_ATTEMPTS
            ):
                logger.info(
                    "Rescheduling termination due to upload failure (run_id=%s attempt=%s/%s).",
                    run_id,
                    attempt_number,
                    _TERMINATION_MAX_UPLOAD_ATTEMPTS,
                )
                await db.reschedule_research_pipeline_run_termination(
                    run_id=run_id,
                    attempts=attempt_number,
                    error=upload_failed_error,
                )
                updated = await db.get_research_pipeline_run_termination(run_id=run_id)
                publish_termination_status_event(run_id=run_id, termination=updated)
                return
            if upload_failed_error is not None:
                logger.warning(
                    "Proceeding to pod termination despite upload failure (run_id=%s attempt=%s/%s).",
                    run_id,
                    attempt_number,
                    _TERMINATION_MAX_UPLOAD_ATTEMPTS,
                )
        elif termination.artifacts_uploaded_at is not None:
            logger.debug("Artifacts already uploaded; skipping upload (run_id=%s).", run_id)
        else:
            logger.debug(
                "Skipping upload due to attempt limit (run_id=%s attempt=%s/%s).",
                run_id,
                attempt_number,
                _TERMINATION_MAX_UPLOAD_ATTEMPTS,
            )

        # Step B: terminate pod (always attempt on final attempt even if upload failed).
        if run.pod_id:
            try:
                logger.info("Terminating pod (run_id=%s pod_id=%s).", run_id, run.pod_id)
                await self._runpod_manager.delete_pod(run.pod_id)
                await db.mark_research_pipeline_run_termination_pod_terminated(run_id=run_id)
                logger.info(
                    "Pod termination acknowledged (run_id=%s pod_id=%s).", run_id, run.pod_id
                )
            except RunPodError as exc:
                if exc.status == 404:
                    logger.info(
                        "Pod already gone (404); treating as terminated (run_id=%s pod_id=%s).",
                        run_id,
                        run.pod_id,
                    )
                    await db.mark_research_pipeline_run_termination_pod_terminated(run_id=run_id)
                else:
                    error_message = (
                        f"RunPod pod termination failed for run {run_id} "
                        f"(pod_id={run.pod_id}, status={exc.status}): {exc}"
                    )
                    logger.warning("%s", error_message)
                    if attempt_number < _TERMINATION_MAX_UPLOAD_ATTEMPTS:
                        logger.info(
                            "Rescheduling termination due to pod termination error (run_id=%s attempt=%s/%s).",
                            run_id,
                            attempt_number,
                            _TERMINATION_MAX_UPLOAD_ATTEMPTS,
                        )
                        await db.reschedule_research_pipeline_run_termination(
                            run_id=run_id,
                            attempts=attempt_number,
                            error=error_message,
                        )
                        updated = await db.get_research_pipeline_run_termination(run_id=run_id)
                        publish_termination_status_event(run_id=run_id, termination=updated)
                        return

                    sentry_sdk.capture_message(error_message, level="error")
                    await db.mark_research_pipeline_run_termination_failed(
                        run_id=run_id,
                        attempts=attempt_number,
                        error=error_message,
                    )
                    updated = await db.get_research_pipeline_run_termination(run_id=run_id)
                    publish_termination_status_event(run_id=run_id, termination=updated)
                    logger.warning(
                        "Termination failed; emitting complete (run_id=%s status=%s).",
                        run_id,
                        run.status,
                    )
                    publish_stream_event(
                        run_id,
                        SSECompleteEvent(
                            type="complete",
                            data=ResearchRunCompleteData(
                                status=cast(
                                    Literal[
                                        "pending",
                                        "running",
                                        "completed",
                                        "failed",
                                        "cancelled",
                                    ],
                                    run.status,
                                ),
                                success=run.status == "completed",
                                message=run.error_message,
                            ),
                        ),
                    )
                    return
        else:
            logger.info(
                "Run has no pod_id; treating as terminated (run_id=%s).",
                run_id,
            )
            await db.mark_research_pipeline_run_termination_pod_terminated(run_id=run_id)

        logger.info("Marking termination as terminated (run_id=%s).", run_id)
        await db.mark_research_pipeline_run_termination_terminated(
            run_id=run_id,
            attempts=attempt_number,
        )
        updated = await db.get_research_pipeline_run_termination(run_id=run_id)
        publish_termination_status_event(run_id=run_id, termination=updated)

        if upload_failed_error is not None and attempt_number >= _TERMINATION_MAX_UPLOAD_ATTEMPTS:
            sentry_sdk.capture_message(
                f"Run {run_id} terminated without successful artifact upload: {upload_failed_error}",
                level="warning",
            )
            logger.warning(
                "Run terminated without successful artifact upload (run_id=%s).",
                run_id,
            )

        if run.pod_id:
            logger.info(
                "Recording pod billing summary (run_id=%s pod_id=%s).",
                run_id,
                run.pod_id,
            )
            await self._record_pod_billing_event(
                db=db,
                run_id=run_id,
                pod_id=run.pod_id,
                context="termination_worker",
            )

        logger.info(
            "Termination complete; emitting complete SSE (run_id=%s status=%s).", run_id, run.status
        )
        publish_stream_event(
            run_id,
            SSECompleteEvent(
                type="complete",
                data=ResearchRunCompleteData(
                    status=cast(
                        Literal[
                            "pending",
                            "running",
                            "completed",
                            "failed",
                            "cancelled",
                        ],
                        run.status,
                    ),
                    success=run.status == "completed",
                    message=run.error_message,
                ),
            ),
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


def _require_int(name: str) -> int:
    value = os.environ.get(name)
    if value is None:
        raise RuntimeError(f"Environment variable {name} is required for pipeline monitoring.")
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer.") from exc


DEFAULT_POLL_INTERVAL_SECONDS = _require_int("PIPELINE_MONITOR_POLL_INTERVAL_SECONDS")
DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = _require_int("PIPELINE_MONITOR_HEARTBEAT_TIMEOUT_SECONDS")
DEFAULT_MAX_MISSED_HEARTBEATS = _require_int("PIPELINE_MONITOR_MAX_MISSED_HEARTBEATS")
DEFAULT_STARTUP_GRACE_SECONDS = _require_int("PIPELINE_MONITOR_STARTUP_GRACE_SECONDS")
DEFAULT_MAX_RUNTIME_HOURS = _require_int("PIPELINE_MONITOR_MAX_RUNTIME_HOURS")

pipeline_monitor = ResearchPipelineMonitor(
    poll_interval_seconds=DEFAULT_POLL_INTERVAL_SECONDS,
    heartbeat_timeout_seconds=DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    max_missed_heartbeats=DEFAULT_MAX_MISSED_HEARTBEATS,
    startup_grace_seconds=DEFAULT_STARTUP_GRACE_SECONDS,
    max_runtime_hours=DEFAULT_MAX_RUNTIME_HOURS,
)
