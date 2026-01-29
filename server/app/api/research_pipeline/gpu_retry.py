"""GPU shortage retry logic for research pipeline runs."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import sentry_sdk

from app.api.research_pipeline_runs import (
    IdeaPayloadSource,
    PodLaunchError,
    create_and_launch_research_run,
)
from app.services.research_pipeline.runpod import get_supported_gpu_types
from app.services.research_pipeline.runpod.runpod_initialization import WORKSPACE_PATH

from .auth import ResearchRunStore, resolve_run_owner_first_name
from .schemas import DiskUsagePartition

logger = logging.getLogger(__name__)

LOW_FREE_DISK_THRESHOLD_BYTES = 50 * 1024**3
BYTES_PER_GB = 1024**3


def resolve_partition_capacity_bytes(
    *,
    container_disk_gb: int | None,
    volume_disk_gb: int | None,
    partition: str,
) -> int | None:
    """Resolve the total capacity in bytes for a given partition."""
    normalized = partition if partition == "/" else partition.rstrip("/")
    if not normalized:
        normalized = "/"
    if normalized == "/":
        capacity_gb = container_disk_gb
    elif normalized == WORKSPACE_PATH:
        capacity_gb = volume_disk_gb
    else:
        return None
    if capacity_gb is None:
        return None
    return int(capacity_gb) * BYTES_PER_GB


async def record_disk_usage_event(
    *,
    db: ResearchRunStore,
    run_id: str,
    partitions: Sequence[DiskUsagePartition],
    occurred_at: datetime,
    event_type: str,
) -> None:
    """Record disk usage event and warn on low disk space."""
    if not partitions:
        return
    partitions_payload = []
    low_free_partitions: list[tuple[str, int]] = []
    for partition in partitions:
        free_bytes = max(partition.total_bytes - partition.used_bytes, 0)
        partitions_payload.append(
            {
                "partition": partition.partition,
                "total_bytes": partition.total_bytes,
                "used_bytes": partition.used_bytes,
                "free_bytes": free_bytes,
            }
        )
        if free_bytes < LOW_FREE_DISK_THRESHOLD_BYTES:
            low_free_partitions.append((partition.partition, free_bytes))
    await db.insert_research_pipeline_run_event(
        run_id=run_id,
        event_type=event_type,
        metadata={"partitions": partitions_payload},
        occurred_at=occurred_at,
    )
    if low_free_partitions:
        details = ", ".join(
            f"{name}={free_bytes / (1024**3):.1f} GiB free"
            for name, free_bytes in low_free_partitions
        )
        message = f"Low disk space detected for run {run_id}: {details}"
        logger.warning(message)
        sentry_sdk.capture_message(message, level="warning")


@dataclass(frozen=True)
class RetryIdeaPayload(IdeaPayloadSource):
    """Payload for retrying a run after GPU shortage."""

    idea_id: int
    version_id: int
    version_number: int
    title: str
    idea_markdown: str


async def retry_run_after_gpu_shortage(
    *,
    db: ResearchRunStore,
    failed_run_id: str,
    failed_run_gpu_type: str | None,
    idea_version_id: int,
) -> None:
    """Attempt to retry a run after a GPU shortage by launching on alternate hardware."""
    idea_version = await db.get_idea_version_by_id(idea_version_id)
    if idea_version is None:
        logger.warning(
            "Cannot retry run %s after GPU shortage: idea version %s not found.",
            failed_run_id,
            idea_version_id,
        )
        return
    idea_payload = RetryIdeaPayload(
        idea_id=idea_version.idea_id,
        version_id=idea_version.version_id,
        version_number=idea_version.version_number,
        title=idea_version.title,
        idea_markdown=idea_version.idea_markdown,
    )
    requester_first_name = await resolve_run_owner_first_name(db=db, run_id=failed_run_id)
    retry_gpu_types = build_retry_gpu_preferences(
        failed_run_gpu_type=failed_run_gpu_type, run_id=failed_run_id
    )

    # Get parent run ID if this conversation is seeded from a previous run
    parent_run_id = await db.get_conversation_parent_run_id(idea_version.conversation_id)

    try:
        new_run_id, _pod_info = await create_and_launch_research_run(
            idea_data=idea_payload,
            requested_by_first_name=requester_first_name,
            gpu_types=retry_gpu_types,
            conversation_id=idea_version.conversation_id,
            parent_run_id=parent_run_id,
        )
        logger.debug(
            "Scheduled retry run %s after GPU shortage on run %s.",
            new_run_id,
            failed_run_id,
        )
        await db.insert_research_pipeline_run_event(
            run_id=failed_run_id,
            event_type="gpu_shortage_retry",
            metadata={
                "retry_run_id": new_run_id,
                "reason": "gpu_shortage",
            },
            occurred_at=datetime.now(timezone.utc),
        )
    except PodLaunchError:
        logger.exception(
            "Failed to schedule retry run after GPU shortage for run %s", failed_run_id
        )
        return


def build_retry_gpu_preferences(
    *, failed_run_gpu_type: str | None, run_id: str | None
) -> list[str]:
    """Return a GPU preference list that reuses the user's original choice when possible."""
    supported_gpu_types = get_supported_gpu_types()
    if not failed_run_gpu_type:
        logger.debug(
            "GPU shortage retry for run %s: no prior GPU recorded; using default list %s.",
            run_id,
            supported_gpu_types,
        )
        return supported_gpu_types

    if failed_run_gpu_type in supported_gpu_types:
        logger.debug(
            "GPU shortage retry for run %s: reusing original GPU type %s.",
            run_id,
            failed_run_gpu_type,
        )
        return [failed_run_gpu_type]

    # If the GPU has been removed from the supported list, still try it first before falling back.
    logger.debug(
        (
            "GPU shortage retry for run %s: requested GPU %s no longer in supported list; "
            "trying it first, then falling back to %s."
        ),
        run_id,
        failed_run_gpu_type,
        supported_gpu_types,
    )
    return [failed_run_gpu_type, *supported_gpu_types]
