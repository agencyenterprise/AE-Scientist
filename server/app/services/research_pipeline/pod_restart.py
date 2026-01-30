"""
Pod restart logic for research pipeline runs.

Handles automatic pod restart when heartbeats are missed, GPU errors occur,
or GPU shortage is detected.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from app.api.research_pipeline_stream import publish_stream_event
from app.models import ResearchRunEvent
from app.models.sse import ResearchRunRunEvent as SSERunEvent
from app.services.database import DatabaseManager
from app.services.database.research_pipeline_runs import PodUpdateInfo, ResearchPipelineRun
from app.services.research_pipeline.runpod import (
    PodLaunchInfo,
    RunPodError,
    fetch_pod_ready_metadata,
    get_pipeline_startup_grace_seconds,
    launch_research_pipeline_run,
    terminate_pod,
)

logger = logging.getLogger(__name__)

# Environment variable for max restart attempts (default: 2)
MAX_RESTART_ATTEMPTS_ENV = "PIPELINE_MAX_RESTART_ATTEMPTS"
DEFAULT_MAX_RESTART_ATTEMPTS = 2


def get_max_restart_attempts() -> int:
    """Get the maximum number of restart attempts from environment."""
    raw = os.environ.get(MAX_RESTART_ATTEMPTS_ENV)
    if raw is None:
        return DEFAULT_MAX_RESTART_ATTEMPTS
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning(
            "Invalid %s=%s; defaulting to %s",
            MAX_RESTART_ATTEMPTS_ENV,
            raw,
            DEFAULT_MAX_RESTART_ATTEMPTS,
        )
        return DEFAULT_MAX_RESTART_ATTEMPTS


async def attempt_pod_restart(
    *,
    db: "DatabaseManager",
    run: ResearchPipelineRun,
    reason: str,
    gpu_types: list[str],
    webhook_token: str,
    webhook_token_hash: str,
) -> bool:
    """
    Attempt to restart a pod for a research run.

    Args:
        db: Database manager instance
        run: The research pipeline run to restart
        reason: The reason for the restart ("heartbeat_timeout", "container_died", or "gpu_shortage")
        gpu_types: List of GPU types to try for the new pod.
        webhook_token: Plain webhook token to pass to the new pod.
        webhook_token_hash: Hash of the webhook token to store in the database.

    Returns:
        True if restart was initiated successfully, False if restart
        should not be attempted (max attempts exceeded, etc.)
    """
    max_restarts = get_max_restart_attempts()

    if run.restart_count >= max_restarts:
        logger.warning(
            "Run %s has reached max restart attempts (%s/%s); will not restart.",
            run.run_id,
            run.restart_count,
            max_restarts,
        )
        return False

    logger.info(
        "Initiating pod restart for run %s (attempt %s/%s, reason=%s)",
        run.run_id,
        run.restart_count + 1,
        max_restarts,
        reason,
    )

    # Step 1: Terminate the old pod (best effort)
    old_pod_id = run.pod_id
    if old_pod_id:
        try:
            await terminate_pod(pod_id=old_pod_id)
            logger.info("Terminated old pod %s for run %s", old_pod_id, run.run_id)
        except Exception as exc:
            logger.warning(
                "Failed to terminate old pod %s for run %s: %s (continuing with restart)",
                old_pod_id,
                run.run_id,
                exc,
            )

    # Step 2: Get the idea data needed to relaunch
    idea_data = await db.get_run_idea_data(run.run_id)
    if idea_data is None:
        logger.error("Cannot restart run %s: idea data not found", run.run_id)
        return False

    # Step 3: Launch new pod (preserve original pod name by extracting username)
    # Pod name format: "aescientist_{username}_{run_id}"
    original_username = "User"
    if run.pod_name:
        parts = run.pod_name.split("_", 2)
        if len(parts) >= 2:
            original_username = parts[1]

    try:
        pod_info = await launch_research_pipeline_run(
            title=idea_data["title"],
            idea=idea_data["idea_markdown"],
            config_name=f"{run.run_id}_config.yaml",
            run_id=run.run_id,
            requested_by_first_name=original_username,
            gpu_types=gpu_types,
            parent_run_id=None,
            webhook_token=webhook_token,
        )

        logger.info(
            "Created new pod %s for run %s restart (gpu=%s, cost=%s)",
            pod_info.pod_id,
            run.run_id,
            pod_info.gpu_type,
            pod_info.cost,
        )

    except (RunPodError, RuntimeError) as exc:
        logger.error(
            "Failed to create new pod for run %s restart: %s",
            run.run_id,
            exc,
        )
        return False

    # Step 5: Update run with new pod info and reset heartbeat tracking
    now = datetime.now(timezone.utc)
    startup_grace = get_pipeline_startup_grace_seconds()

    await db.update_research_pipeline_run(
        run_id=run.run_id,
        pod_update_info=PodUpdateInfo(
            pod_id=pod_info.pod_id,
            pod_name=pod_info.pod_name,
            gpu_type=pod_info.gpu_type,
            cost=pod_info.cost,
            public_ip=None,
            ssh_port=None,
            pod_host_id=None,
        ),
        last_heartbeat_at=None,
        heartbeat_failures=0,
        restart_count=run.restart_count + 1,
        last_restart_at=now,
        last_restart_reason=reason,
        start_deadline_at=now + timedelta(seconds=startup_grace),
        status="initializing",
        initialization_status="Restarting pod",
        webhook_token_hash=webhook_token_hash,
    )

    # Step 6: Record restart event
    await db.insert_research_pipeline_run_event(
        run_id=run.run_id,
        event_type="pod_restarted",
        metadata={
            "old_pod_id": old_pod_id,
            "new_pod_id": pod_info.pod_id,
            "restart_count": run.restart_count + 1,
            "reason": reason,
            "gpu_type": pod_info.gpu_type,
            "cost_per_hr": pod_info.cost,
        },
        occurred_at=now,
    )

    # Step 7: Publish SSE event for UI update
    run_event = ResearchRunEvent(
        id=int(now.timestamp() * 1000),
        run_id=run.run_id,
        event_type="pod_restarted",
        metadata={
            "old_pod_id": old_pod_id,
            "new_pod_id": pod_info.pod_id,
            "restart_count": run.restart_count + 1,
            "reason": reason,
        },
        occurred_at=now.isoformat(),
    )
    publish_stream_event(
        run.run_id,
        SSERunEvent(type="run_event", data=run_event),
    )

    # Step 8: Start background task to wait for new pod readiness
    asyncio.create_task(
        _wait_for_restarted_pod_ready(
            db=db,
            run_id=run.run_id,
            pod_info=pod_info,
        )
    )

    logger.info(
        "Pod restart initiated for run %s: old=%s new=%s",
        run.run_id,
        old_pod_id,
        pod_info.pod_id,
    )
    return True


async def _wait_for_restarted_pod_ready(
    *,
    db: "DatabaseManager",
    run_id: str,
    pod_info: PodLaunchInfo,
) -> None:
    """Background task to update run with SSH info once restarted pod is ready."""
    try:
        ready_metadata = await fetch_pod_ready_metadata(pod_id=pod_info.pod_id)

        await db.update_research_pipeline_run(
            run_id=run_id,
            pod_update_info=PodUpdateInfo(
                pod_id=pod_info.pod_id,
                pod_name=pod_info.pod_name,
                gpu_type=pod_info.gpu_type,
                cost=pod_info.cost,
                public_ip=ready_metadata.public_ip,
                ssh_port=ready_metadata.ssh_port,
                pod_host_id=ready_metadata.pod_host_id,
            ),
        )
        logger.info(
            "Restarted pod %s ready for run %s: ip=%s port=%s",
            pod_info.pod_id,
            run_id,
            ready_metadata.public_ip,
            ready_metadata.ssh_port,
        )
    except Exception as exc:
        logger.warning(
            "Failed to get ready metadata for restarted pod %s (run=%s): %s",
            pod_info.pod_id,
            run_id,
            exc,
        )
