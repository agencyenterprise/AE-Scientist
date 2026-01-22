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
from typing import Literal, Optional, Protocol, cast

import sentry_sdk

from app.api.research_pipeline_stream import publish_stream_event
from app.models.sse import ResearchRunCompleteData
from app.models.sse import ResearchRunCompleteEvent as SSECompleteEvent
from app.models.sse import ResearchRunTerminationStatusData, ResearchRunTerminationStatusEvent
from app.services import get_database
from app.services.database.research_pipeline_run_termination import ResearchPipelineRunTermination
from app.services.database.research_pipeline_runs import ResearchPipelineRun
from app.services.research_pipeline.runpod import (
    RunPodError,
    RunPodManager,
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
        if run.pod_id:
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

        logger.info(
            "Termination complete; emitting complete SSE (run_id=%s status=%s).",
            run_id,
            run.status,
        )
        publish_stream_event(
            run_id,
            SSECompleteEvent(
                type="complete",
                data=ResearchRunCompleteData(
                    status=cast(
                        Literal["pending", "running", "completed", "failed", "cancelled"],
                        run.status,
                    ),
                    success=run.status == "completed",
                    message=run.error_message,
                ),
            ),
        )
