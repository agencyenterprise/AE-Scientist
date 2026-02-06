"""
Background worker that processes pending RunPod termination jobs.

This module provides:
- A lease-based queue worker (`PodTerminationWorker`) that claims termination rows from the
  database, performs best-effort artifact upload over SSH, then terminates the RunPod pod.
- A wakeup signal (`notify_termination_requested`, `get_termination_wakeup_event`) so API
  handlers can prompt the worker to re-poll immediately.
- SSE helpers (`publish_termination_status_event`) that emit termination status updates to
  clients based on `ResearchPipelineRunTermination` state.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Literal, Optional, Protocol, cast

import sentry_sdk

from app.api.research_pipeline_event_stream import usd_to_cents
from app.api.research_pipeline_stream import publish_stream_event
from app.models.research_pipeline import ResearchRunEvent
from app.models.sse import ResearchRunCompleteData
from app.models.sse import ResearchRunCompleteEvent as SSECompleteEvent
from app.models.sse import ResearchRunRunEvent as SSERunEvent
from app.models.sse import ResearchRunTerminationStatusData, ResearchRunTerminationStatusEvent
from app.services import DatabaseManager, get_database
from app.services.billing_guard import charge_cents
from app.services.database.research_pipeline_run_termination import ResearchPipelineRunTermination
from app.services.database.research_pipeline_runs import ResearchPipelineRun
from app.services.research_pipeline.runpod import (
    RunPodError,
    RunPodManager,
    fetch_pod_billing_summary,
    upload_runpod_artifacts_via_ssh,
)

logger = logging.getLogger(__name__)

_TERMINATION_MAX_UPLOAD_ATTEMPTS = 3
_TERMINATION_LEASE_SECONDS = 50 * 60
_TERMINATION_STUCK_SECONDS = 60 * 60

_termination_wakeup_event = asyncio.Event()


def notify_termination_requested() -> None:
    _termination_wakeup_event.set()


def get_termination_wakeup_event() -> asyncio.Event:
    return _termination_wakeup_event


async def _record_pod_billing_event(
    db: DatabaseManager,
    *,
    run_id: str,
    pod_id: str,
    context: str,
) -> bool:
    """
    Record pod billing event and reconcile billing.

    Returns True if billing was successfully charged (actual cost obtained),
    False if billing data was empty/missing and needs retry.
    """
    try:
        summary = await fetch_pod_billing_summary(pod_id=pod_id)
    except (RuntimeError, RunPodError):
        logger.exception("Failed to fetch billing summary for pod %s", pod_id)
        # Mark run as awaiting billing data so it can be retried
        await db.update_research_pipeline_run(
            run_id=run_id,
            hw_billing_status="awaiting_billing_data",
            hw_billing_last_retry_at=datetime.now(timezone.utc),
        )
        return False

    # Check if we got empty/missing billing data from RunPod
    if summary is None or not summary.records or summary.total_amount_usd == 0:
        logger.warning(
            "RunPod returned empty billing data for pod %s (run_id=%s). "
            "Marking for billing retry.",
            pod_id,
            run_id,
        )
        # Mark run as awaiting billing data - holds remain in place
        await db.update_research_pipeline_run(
            run_id=run_id,
            hw_billing_status="awaiting_billing_data",
            hw_billing_last_retry_at=datetime.now(timezone.utc),
        )
        return False

    metadata = summary._asdict()
    metadata["records"] = [record._asdict() for record in summary.records]
    metadata["context"] = context
    actual_cost_cents: int | None = None
    total_amount = summary.total_amount_usd

    try:
        actual_cost_cents = usd_to_cents(value_usd=float(total_amount))
    except (TypeError, ValueError):
        pass
    if actual_cost_cents is not None:
        metadata["actual_cost_cents"] = actual_cost_cents

    # Reconcile billing: reverse holds and charge actual cost
    if actual_cost_cents is not None:
        user_id = await db.get_run_owner_user_id(run_id)
        if user_id is not None:
            try:
                # Reverse all "hold" transactions for this run
                reversed_amount = await db.reverse_hold_transactions(run_id=run_id)
                logger.debug(
                    "Reversed %d cents in hold transactions for run %s",
                    reversed_amount,
                    run_id,
                )
                metadata["holds_reversed_cents"] = reversed_amount

                # Charge the actual GPU cost
                if actual_cost_cents > 0:
                    await charge_cents(
                        user_id=user_id,
                        amount_cents=actual_cost_cents,
                        action="research_run_gpu",
                        description=f"Research run {run_id} GPU cost (final)",
                        metadata={
                            "run_id": run_id,
                            "pod_id": pod_id,
                            "total_amount_usd": str(total_amount),
                        },
                    )
                    logger.debug(
                        "Charged %d cents for run %s GPU cost (final)",
                        actual_cost_cents,
                        run_id,
                    )

                # Mark billing as successfully charged
                await db.update_research_pipeline_run(
                    run_id=run_id,
                    hw_billing_status="charged",
                )
            except Exception as billing_error:
                logger.exception(
                    "Failed to reconcile billing for run %s: %s",
                    run_id,
                    billing_error,
                )
                # Mark as awaiting billing data so it can be retried
                await db.update_research_pipeline_run(
                    run_id=run_id,
                    hw_billing_status="awaiting_billing_data",
                    hw_billing_last_retry_at=datetime.now(timezone.utc),
                )
                return False

    now = datetime.now(timezone.utc)
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type="pod_billing_summary",
        metadata=metadata,
        occurred_at=now,
    )
    run_event = ResearchRunEvent(
        id=int(now.timestamp() * 1000),
        run_id=run_id,
        event_type="pod_billing_summary",
        metadata=metadata,
        occurred_at=now.isoformat(),
    )
    publish_stream_event(
        run_id,
        SSERunEvent(
            type="run_event",
            data=run_event,
        ),
    )
    return True


def build_termination_status_payload(
    *,
    termination: ResearchPipelineRunTermination | None,
) -> dict[str, object]:
    if termination is None:
        return {"status": "none", "last_error": None}

    return {
        "status": termination.status,
        "last_error": termination.last_error,
    }


def publish_termination_status_event(
    *,
    run_id: str,
    termination: ResearchPipelineRunTermination | None,
) -> None:
    data = build_termination_status_payload(termination=termination)
    publish_stream_event(
        run_id,
        ResearchRunTerminationStatusEvent(
            type="termination_status",
            data=ResearchRunTerminationStatusData(
                status=cast(
                    Literal["none", "requested", "in_progress", "terminated", "failed"],
                    data["status"],
                ),
                last_error=cast(str | None, data.get("last_error")),
            ),
        ),
    )


class PodTerminationStore(Protocol):
    async def get_research_pipeline_run(self, run_id: str) -> Optional[ResearchPipelineRun]: ...

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

    async def reset_stale_termination_leases(self) -> int: ...


class PodTerminationWorker:
    def __init__(
        self,
        *,
        runpod_manager: RunPodManager,
        max_concurrency: int,
        poll_interval_seconds: int,
    ) -> None:
        self._runpod_manager = runpod_manager
        self._max_concurrency = max_concurrency
        self._poll_interval_seconds = poll_interval_seconds
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._inflight: set[str] = set()
        self._queue: asyncio.Queue[ResearchPipelineRunTermination] = asyncio.Queue()

    async def run(self, *, stop_event: asyncio.Event) -> None:
        lease_owner = f"pipeline_monitor:{os.getpid()}"

        # Reset any in_progress terminations from previous workers that may have
        # died (e.g., due to deployment). This ensures orphaned jobs are reclaimed.
        db = cast("PodTerminationStore", get_database())
        reset_count = await db.reset_stale_termination_leases()
        if reset_count > 0:
            logger.info(
                "Reset %s stale termination lease(s) from previous worker(s).",
                reset_count,
            )

        logger.info(
            "Pod termination worker started (max_concurrency=%s max_attempts=%s lease_owner=%s lease_seconds=%s stuck_seconds=%s).",
            self._max_concurrency,
            _TERMINATION_MAX_UPLOAD_ATTEMPTS,
            lease_owner,
            _TERMINATION_LEASE_SECONDS,
            _TERMINATION_STUCK_SECONDS,
        )
        feeder_task = asyncio.create_task(
            self._run_queue_feeder(stop_event=stop_event, lease_owner=lease_owner),
            name="PodTerminationQueueFeeder",
        )
        tasks: set[asyncio.Task[None]] = {feeder_task}
        try:
            while not stop_event.is_set():
                stop_task = asyncio.create_task(stop_event.wait())
                get_task = asyncio.create_task(self._queue.get())
                done, pending = await asyncio.wait(
                    fs={stop_task, get_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()

                # If we race between stop and queue.get(), avoid dropping the dequeued job.
                if stop_task in done and get_task in done:
                    termination = get_task.result()
                    self._queue.put_nowait(termination)
                    break

                if stop_task in done:
                    break

                termination = get_task.result()

                run_id = termination.run_id
                if run_id in self._inflight:
                    logger.debug(
                        "Skipping duplicate termination already in-flight (run_id=%s).",
                        run_id,
                    )
                    continue

                self._inflight.add(run_id)
                job_task = asyncio.create_task(
                    self._run_job(termination=termination),
                    name=f"PodTerminationJob:{run_id}",
                )
                tasks.add(job_task)
                job_task.add_done_callback(tasks.discard)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_queue_feeder(self, *, stop_event: asyncio.Event, lease_owner: str) -> None:
        wakeup_event = get_termination_wakeup_event()
        while not stop_event.is_set():
            wakeup_event.clear()
            await self._claim_and_enqueue_terminations(lease_owner=lease_owner)

            stop_task = asyncio.create_task(stop_event.wait())
            wake_task = asyncio.create_task(wakeup_event.wait())
            try:
                done, pending = await asyncio.wait(
                    fs={stop_task, wake_task},
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=self._poll_interval_seconds,
                )
                for task in pending:
                    task.cancel()
                if stop_task in done:
                    return
            finally:
                stop_task.cancel()
                wake_task.cancel()

    async def _claim_and_enqueue_terminations(self, *, lease_owner: str) -> None:
        db = cast("PodTerminationStore", get_database())
        claimed = 0
        while True:
            termination = await db.claim_research_pipeline_run_termination(
                lease_owner=lease_owner,
                lease_seconds=_TERMINATION_LEASE_SECONDS,
                stuck_seconds=_TERMINATION_STUCK_SECONDS,
            )
            if termination is None:
                break
            claimed += 1
            logger.info(
                "Enqueuing termination job (run_id=%s status=%s attempts=%s artifacts_uploaded=%s pod_terminated=%s).",
                termination.run_id,
                termination.status,
                termination.attempts,
                bool(termination.artifacts_uploaded_at),
                bool(termination.pod_terminated_at),
            )
            await self._queue.put(termination)
        if claimed:
            logger.info("Enqueued %s termination job(s).", claimed)

    async def _run_job(self, *, termination: ResearchPipelineRunTermination) -> None:
        run_id = termination.run_id
        async with self._semaphore:
            try:
                db = cast("PodTerminationStore", get_database())
            except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                logger.exception(
                    "Failed to acquire database handle for termination job (run_id=%s).",
                    run_id,
                )
                return

            try:
                logger.info(
                    "Starting termination job (run_id=%s status=%s attempts=%s artifacts_uploaded=%s pod_terminated=%s).",
                    run_id,
                    termination.status,
                    termination.attempts,
                    bool(termination.artifacts_uploaded_at),
                    bool(termination.pod_terminated_at),
                )
                await self._process_termination(db=db, termination=termination)
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                logger.exception("Unhandled termination worker error (run_id=%s).", run_id)
                try:
                    await self._handle_job_exception(
                        db=db,
                        termination=termination,
                        exc=exc,
                    )
                except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                    logger.exception(
                        "Failed to handle termination worker error (run_id=%s).",
                        run_id,
                    )
            finally:
                self._inflight.discard(run_id)

    async def _handle_job_exception(
        self,
        *,
        db: PodTerminationStore,
        termination: ResearchPipelineRunTermination,
        exc: Exception,
    ) -> None:
        run_id = termination.run_id
        attempt_number = int(termination.attempts or 0) + 1
        error_message = f"Unhandled termination worker error for run {run_id}: {exc}"
        if attempt_number < _TERMINATION_MAX_UPLOAD_ATTEMPTS:
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

    async def _process_termination(
        self,
        *,
        db: PodTerminationStore,
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
                attempts=int(termination.attempts or 0) + 1,
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
                        run_id=run_id,
                    )
                    logger.info("Artifacts upload succeeded (run_id=%s).", run_id)
                except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
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
        try:
            logger.info("Terminating pod (run_id=%s pod_id=%s).", run_id, run.pod_id)
            await self._runpod_manager.delete_pod(run.pod_id)
            await db.mark_research_pipeline_run_termination_pod_terminated(run_id=run_id)
            logger.info(
                "Pod termination acknowledged (run_id=%s pod_id=%s).",
                run_id,
                run.pod_id,
            )
        except RunPodError as exc:
            logger.exception(
                "RunPod pod termination threw an exception (run_id=%s pod_id=%s status=%s).",
                run_id,
                run.pod_id,
                exc.status,
            )
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
                # Map status to valid SSE status values
                early_sse_status: Literal["pending", "running", "completed", "failed", "cancelled"]
                if run.status == "initializing":
                    # If terminated during initialization, treat as cancelled
                    early_sse_status = "cancelled"
                elif run.status in ("pending", "running", "completed", "failed", "cancelled"):
                    early_sse_status = cast(
                        Literal["pending", "running", "completed", "failed", "cancelled"],
                        run.status,
                    )
                else:
                    # Unknown status, default to failed
                    early_sse_status = "failed"

                publish_stream_event(
                    run_id,
                    SSECompleteEvent(
                        type="complete",
                        data=ResearchRunCompleteData(
                            status=early_sse_status,
                            success=run.status == "completed",
                            message=run.error_message,
                        ),
                    ),
                )
                return

        logger.info("Marking termination as terminated (run_id=%s).", run_id)
        await db.mark_research_pipeline_run_termination_terminated(
            run_id=run_id,
            attempts=attempt_number,
        )
        updated = await db.get_research_pipeline_run_termination(run_id=run_id)
        publish_termination_status_event(run_id=run_id, termination=updated)

        # Record pod billing summary now that termination is complete
        billing_context = termination.last_trigger or "termination_worker"
        logger.info(
            "Recording pod billing summary (run_id=%s pod_id=%s context=%s).",
            run_id,
            run.pod_id,
            billing_context,
        )
        try:
            # Cast db to DatabaseManager for billing function
            await _record_pod_billing_event(
                cast(DatabaseManager, db),
                run_id=run_id,
                pod_id=run.pod_id,
                context=billing_context,
            )
        except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            # Best-effort billing recording - don't fail termination if it fails
            logger.exception(
                "Failed to record pod billing summary (run_id=%s pod_id=%s).",
                run_id,
                run.pod_id,
            )

        if upload_failed_error is not None and attempt_number >= _TERMINATION_MAX_UPLOAD_ATTEMPTS:
            sentry_sdk.capture_message(
                f"Run {run_id} terminated without successful artifact upload: {upload_failed_error}",
                level="warning",
            )
            logger.warning(
                "Run terminated without successful artifact upload (run_id=%s).",
                run_id,
            )

        logger.info(
            "Termination complete; emitting complete SSE (run_id=%s status=%s).",
            run_id,
            run.status,
        )
        # Map status to valid SSE status values
        sse_status: Literal["pending", "running", "completed", "failed", "cancelled"]
        if run.status == "initializing":
            # If terminated during initialization, treat as cancelled
            sse_status = "cancelled"
        elif run.status in ("pending", "running", "completed", "failed", "cancelled"):
            sse_status = cast(
                Literal["pending", "running", "completed", "failed", "cancelled"],
                run.status,
            )
        else:
            # Unknown status, default to failed
            sse_status = "failed"

        publish_stream_event(
            run_id,
            SSECompleteEvent(
                type="complete",
                data=ResearchRunCompleteData(
                    status=sse_status,
                    success=run.status == "completed",
                    message=run.error_message,
                ),
            ),
        )


async def retry_billing_for_run(
    db: DatabaseManager,
    *,
    run: ResearchPipelineRun,
    max_retries: int = 10,
) -> bool:
    """
    Retry fetching billing data from RunPod for a run that is awaiting billing data.

    This is called by the billing retry daemon for runs where RunPod initially
    returned empty billing data at pod termination.

    Args:
        db: Database manager instance
        run: The research pipeline run to retry billing for
        max_retries: Maximum number of retry attempts before falling back to estimated cost

    Returns:
        True if billing was successfully reconciled, False if retry failed or needs more retries
    """
    run_id = run.run_id
    pod_id = run.pod_id
    retry_count = run.hw_billing_retry_count + 1

    logger.info(
        "Retrying billing for run %s (pod_id=%s, attempt=%s/%s)",
        run_id,
        pod_id,
        retry_count,
        max_retries,
    )

    if not pod_id:
        logger.warning(
            "Cannot retry billing for run %s: no pod_id",
            run_id,
        )
        # No pod means no GPU cost - mark as charged with 0 cost
        await db.update_research_pipeline_run(
            run_id=run_id,
            hw_billing_status="charged",
            hw_billing_retry_count=retry_count,
            hw_billing_last_retry_at=datetime.now(timezone.utc),
        )
        return True

    # Update retry tracking
    await db.update_research_pipeline_run(
        run_id=run_id,
        hw_billing_retry_count=retry_count,
        hw_billing_last_retry_at=datetime.now(timezone.utc),
    )

    # Try to get billing data from RunPod
    billing_success = await _record_pod_billing_event(
        db,
        run_id=run_id,
        pod_id=pod_id,
        context=f"billing_retry_attempt_{retry_count}",
    )

    if billing_success:
        logger.info(
            "Billing retry succeeded for run %s after %s attempts",
            run_id,
            retry_count,
        )
        return True

    # Check if we've exhausted retries
    if retry_count >= max_retries:
        logger.warning(
            "Billing retry exhausted for run %s after %s attempts. "
            "Falling back to estimated cost from holds.",
            run_id,
            max_retries,
        )
        # Fall back to estimated cost - the holds already reflect the estimated usage
        # Mark as charged_estimated so we know this was a fallback
        user_id = await db.get_run_owner_user_id(run_id)
        if user_id is not None:
            try:
                # The holds are already applied, so we just need to mark them as final
                # by NOT reversing them. We mark the run as charged_estimated.
                await db.update_research_pipeline_run(
                    run_id=run_id,
                    hw_billing_status="charged_estimated",
                )

                # Record an event noting the fallback
                now = datetime.now(timezone.utc)
                await db.insert_research_pipeline_run_event(
                    run_id=run_id,
                    event_type="billing_fallback",
                    metadata={
                        "reason": "runpod_billing_unavailable",
                        "retry_count": retry_count,
                        "note": "Using estimated cost from hold transactions",
                    },
                    occurred_at=now,
                )

                logger.info(
                    "Marked run %s as charged_estimated (holds retained as final cost)",
                    run_id,
                )
            except Exception as fallback_error:
                logger.exception(
                    "Failed to apply billing fallback for run %s: %s",
                    run_id,
                    fallback_error,
                )
        return True  # We're done with this run (using estimated cost)

    logger.debug(
        "Billing retry failed for run %s, will retry later (attempt %s/%s)",
        run_id,
        retry_count,
        max_retries,
    )
    return False
