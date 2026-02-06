"""
Background worker that retries billing for runs with missing RunPod billing data.

This module provides:
- A worker (`BillingRetryWorker`) that periodically checks for runs where RunPod
  returned empty billing data at pod termination and retries fetching the actual costs.
- When actual costs are obtained, it reverses the hold transactions and charges the real amount.
- After max retries/time are exhausted, it falls back to using the estimated cost from holds.

Retry schedule uses exponential backoff:
- Base interval: 5 minutes
- Max interval: 4 hours (capped)
- Max elapsed time: 48 hours (2 days)
"""

import asyncio
import logging
from datetime import datetime
from typing import Protocol

from app.services.database import DatabaseManager
from app.services.database.research_pipeline_runs import ResearchPipelineRun
from app.services.research_pipeline.pod_termination_worker import retry_billing_for_run

logger = logging.getLogger(__name__)

# Default configuration for exponential backoff billing retries
_DEFAULT_BILLING_RETRY_POLL_INTERVAL_SECONDS = 5 * 60  # Check for eligible runs every 5 minutes
_DEFAULT_BASE_RETRY_INTERVAL_SECONDS = 5 * 60  # 5 minutes base interval (doubles each retry)
_DEFAULT_MAX_RETRY_INTERVAL_SECONDS = 4 * 60 * 60  # Cap at 4 hours between retries
_DEFAULT_MAX_RETRY_COUNT = 30  # Safety limit on retry count
_DEFAULT_MAX_ELAPSED_HOURS = 48  # Stop retrying after 2 days


class BillingRetryStore(Protocol):
    """Protocol for database operations needed by the billing retry worker."""

    async def list_runs_awaiting_billing(
        self,
        *,
        max_retry_count: int = 30,
        base_interval_seconds: int = 300,
        max_interval_seconds: int = 14400,
        max_elapsed_hours: int = 48,
    ) -> list[ResearchPipelineRun]: ...

    async def get_run_owner_user_id(self, run_id: str) -> int | None: ...

    async def update_research_pipeline_run(
        self,
        *,
        run_id: str,
        hw_billing_status: str | None = None,
        hw_billing_last_retry_at: datetime | None = None,
        hw_billing_retry_count: int | None = None,
    ) -> None: ...

    async def insert_research_pipeline_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        metadata: dict[str, object],
        occurred_at: datetime,
    ) -> None: ...


class BillingRetryWorker:
    """Worker that retries billing for runs awaiting billing data from RunPod.

    Uses exponential backoff: interval = min(base * 2^retry_count, max_interval)
    Stops after max_elapsed_hours since run completion or max_retry_count reached.
    """

    def __init__(
        self,
        *,
        db: DatabaseManager,
        poll_interval_seconds: int = _DEFAULT_BILLING_RETRY_POLL_INTERVAL_SECONDS,
        base_interval_seconds: int = _DEFAULT_BASE_RETRY_INTERVAL_SECONDS,
        max_interval_seconds: int = _DEFAULT_MAX_RETRY_INTERVAL_SECONDS,
        max_retry_count: int = _DEFAULT_MAX_RETRY_COUNT,
        max_elapsed_hours: int = _DEFAULT_MAX_ELAPSED_HOURS,
    ) -> None:
        self._db = db
        self._poll_interval_seconds = poll_interval_seconds
        self._base_interval_seconds = base_interval_seconds
        self._max_interval_seconds = max_interval_seconds
        self._max_retry_count = max_retry_count
        self._max_elapsed_hours = max_elapsed_hours

    async def run(self, *, stop_event: asyncio.Event) -> None:
        """Run the billing retry worker until stop_event is set."""
        logger.info(
            "Billing retry worker started (poll=%ss, base_interval=%ss, max_interval=%ss, "
            "max_retries=%s, max_elapsed=%sh)",
            self._poll_interval_seconds,
            self._base_interval_seconds,
            self._max_interval_seconds,
            self._max_retry_count,
            self._max_elapsed_hours,
        )

        while not stop_event.is_set():
            try:
                await self._check_billing_retries()
            except Exception:  # noqa: BLE001
                logger.exception("Billing retry worker encountered an error.")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._poll_interval_seconds)
            except asyncio.TimeoutError:
                continue

        logger.info("Billing retry worker stopped.")

    async def _check_billing_retries(self) -> None:
        """Check for and process runs that need billing retry."""
        runs = await self._db.list_runs_awaiting_billing(
            max_retry_count=self._max_retry_count,
            base_interval_seconds=self._base_interval_seconds,
            max_interval_seconds=self._max_interval_seconds,
            max_elapsed_hours=self._max_elapsed_hours,
        )

        if not runs:
            logger.debug("Billing retry worker: no runs awaiting billing data.")
            return

        logger.info(
            "Billing retry worker found %s run(s) awaiting billing data: %s",
            len(runs),
            [f"{r.run_id}(retry={r.hw_billing_retry_count})" for r in runs],
        )

        for run in runs:
            try:
                success = await retry_billing_for_run(
                    self._db,
                    run=run,
                    max_retries=self._max_retry_count,
                )
                if success:
                    logger.info(
                        "Billing retry succeeded for run %s",
                        run.run_id,
                    )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Billing retry failed for run %s",
                    run.run_id,
                )
