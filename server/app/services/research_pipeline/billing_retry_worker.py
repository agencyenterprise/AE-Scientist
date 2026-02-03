"""
Background worker that retries billing for runs with missing RunPod billing data.

This module provides:
- A worker (`BillingRetryWorker`) that periodically checks for runs where RunPod
  returned empty billing data at pod termination and retries fetching the actual costs.
- When actual costs are obtained, it reverses the hold transactions and charges the real amount.
- After max retries are exhausted, it falls back to using the estimated cost from holds.
"""

import asyncio
import logging
from datetime import datetime
from typing import Protocol

from app.services.database import DatabaseManager
from app.services.database.research_pipeline_runs import ResearchPipelineRun
from app.services.research_pipeline.pod_termination_worker import retry_billing_for_run

logger = logging.getLogger(__name__)

# Default configuration
_DEFAULT_BILLING_RETRY_INTERVAL_SECONDS = 5 * 60  # Check every 5 minutes
_DEFAULT_MIN_RETRY_INTERVAL_SECONDS = 5 * 60  # 5 minutes between retries for same run
_DEFAULT_MAX_RETRY_COUNT = 10


class BillingRetryStore(Protocol):
    """Protocol for database operations needed by the billing retry worker."""

    async def list_runs_awaiting_billing(
        self,
        *,
        max_retry_count: int = 10,
        min_retry_interval_seconds: int = 300,
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
    """Worker that retries billing for runs awaiting billing data from RunPod."""

    def __init__(
        self,
        *,
        db: DatabaseManager,
        poll_interval_seconds: int = _DEFAULT_BILLING_RETRY_INTERVAL_SECONDS,
        min_retry_interval_seconds: int = _DEFAULT_MIN_RETRY_INTERVAL_SECONDS,
        max_retry_count: int = _DEFAULT_MAX_RETRY_COUNT,
    ) -> None:
        self._db = db
        self._poll_interval_seconds = poll_interval_seconds
        self._min_retry_interval_seconds = min_retry_interval_seconds
        self._max_retry_count = max_retry_count

    async def run(self, *, stop_event: asyncio.Event) -> None:
        """Run the billing retry worker until stop_event is set."""
        logger.info(
            "Billing retry worker started (poll_interval=%ss, min_retry_interval=%ss, max_retries=%s)",
            self._poll_interval_seconds,
            self._min_retry_interval_seconds,
            self._max_retry_count,
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
            min_retry_interval_seconds=self._min_retry_interval_seconds,
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
