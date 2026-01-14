"""
Database operations for narrator architecture.

Handles persistence of:
- Timeline events (append-only event log)
- Research run state (computed state snapshot)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from app.models.narrator_state import ResearchRunState
from app.models.timeline_events import TimelineEvent

from .base import ConnectionProvider

logger = logging.getLogger(__name__)

# Type adapter for parsing TimelineEvent union
_timeline_event_adapter: TypeAdapter[TimelineEvent] = TypeAdapter(TimelineEvent)


# ============================================================================
# TIMELINE EVENTS
# ============================================================================


class NarratorMixin(ConnectionProvider):
    """Database operations for narrator architecture."""

    async def insert_timeline_event(
        self,
        *,
        run_id: str,
        event: TimelineEvent,
    ) -> None:
        """
        Insert a timeline event into the database.

        Strips fields that are stored in dedicated columns to avoid duplication.
        On retrieval, these fields are hydrated from the columns.
        """
        event_data = event.model_dump(mode="json")

        # Extract fields that have dedicated columns
        event_id = event_data.pop("id")
        event_type = event_data.pop("type")
        timestamp = event_data.pop("timestamp")
        stage = event_data.pop("stage")
        node_id = event_data.pop("node_id", None)

        # Now event_data only contains event-specific fields

        query = """
            INSERT INTO rp_timeline_events (
                run_id, event_id, event_type, event_data, 
                timestamp, stage, node_id, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
        """

        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    query,
                    (
                        run_id,
                        event_id,
                        event_type,
                        Jsonb(event_data),
                        timestamp,
                        stage,
                        node_id,
                        datetime.now(timezone.utc),
                    ),
                )
                await conn.commit()

        logger.info(
            "Inserted timeline event: run=%s type=%s stage=%s",
            run_id,
            event_type,
            stage,
        )

    async def get_timeline_events(
        self,
        run_id: str,
        *,
        event_type: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> List[TimelineEvent]:
        """
        Get timeline events for a run as Pydantic models.

        Hydrates stripped fields from columns back into event_data,
        then parses into proper TimelineEvent models.
        """
        conditions = ["run_id = %s"]
        params: List[Any] = [run_id]

        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)

        if stage:
            conditions.append("stage = %s")
            params.append(stage)

        where_clause = " AND ".join(conditions)
        query: str = f"""
            SELECT id, run_id, event_id, event_type, event_data, 
                   timestamp, stage, node_id, created_at
            FROM rp_timeline_events
            WHERE {where_clause}
            ORDER BY timestamp ASC, id ASC
        """

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, params)  # pyright: ignore[reportArgumentType]
                rows = await cursor.fetchall() or []

        # Hydrate stripped fields back into event_data and parse as Pydantic models
        events: List[TimelineEvent] = []
        for row in rows:
            event_data = dict(row["event_data"])
            # Re-add the fields that were stripped
            event_data["id"] = row["event_id"]
            event_data["type"] = row["event_type"]
            event_data["timestamp"] = row["timestamp"].isoformat()
            event_data["stage"] = row["stage"]
            event_data["node_id"] = row["node_id"]

            # Parse into proper TimelineEvent Pydantic model
            # TimelineEvent is a discriminated union, use TypeAdapter to validate
            timeline_event = _timeline_event_adapter.validate_python(event_data)
            events.append(timeline_event)

        return events

    # ============================================================================
    # RESEARCH RUN STATE
    # ============================================================================

    async def upsert_research_run_state(
        self,
        *,
        run_id: str,
        state: ResearchRunState,
        expected_version: Optional[int] = None,
        conn: Optional[AsyncConnection[Any]] = None,
    ) -> bool:
        """
        Insert or update research run state.

        Uses optimistic locking via version field.
        If expected_version is provided and doesn't match, update fails.

        Args:
            run_id: Research run ID
            state: Complete research run state
            expected_version: Expected current version (for optimistic locking)
            conn: Optional database connection (if within transaction)

        Returns:
            True if update succeeded, False if version conflict
        """
        # Convert state to dict for JSONB storage
        state_data = state.model_dump(mode="json")

        # Remove timeline from storage (hydrate from rp_timeline_events on fetch)
        # This prevents column bloat as timeline can grow large
        last_event_id = state.timeline[-1].id if state.timeline else None
        state_data["timeline"] = []

        if expected_version is None:
            # Insert or update without version check
            query = """
                INSERT INTO rp_research_run_state (
                    run_id, state_data, version, last_event_id, updated_at, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    state_data = EXCLUDED.state_data,
                    version = rp_research_run_state.version + 1,
                    last_event_id = EXCLUDED.last_event_id,
                    updated_at = EXCLUDED.updated_at
            """
            params: tuple[Any, ...] = (
                run_id,
                Jsonb(state_data),
                state.version,
                last_event_id,
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
            )
        else:
            # Update with version check (optimistic locking)
            query = """
                UPDATE rp_research_run_state
                SET state_data = %s,
                    version = version + 1,
                    last_event_id = %s,
                    updated_at = %s
                WHERE run_id = %s AND version = %s
            """
            params = (
                Jsonb(state_data),
                last_event_id,
                datetime.now(timezone.utc),
                run_id,
                expected_version,
            )

        if conn is not None:
            # Use provided connection (within transaction)
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                rows_affected = cursor.rowcount
        else:
            # Create new connection
            async with self.aget_connection() as new_conn:
                async with new_conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    rows_affected = cursor.rowcount
                    await new_conn.commit()

        if expected_version is not None and rows_affected == 0:
            logger.warning(
                "State update failed due to version conflict: run=%s expected_version=%s",
                run_id,
                expected_version,
            )
            return False

        logger.info(
            "Upserted research run state: run=%s version=%s",
            run_id,
            state.version,
        )
        return True

    async def get_research_run_state(self, run_id: str) -> Optional[ResearchRunState]:
        """
        Get current research run state.

        Hydrates timeline from rp_timeline_events table as proper Pydantic models.

        Args:
            run_id: Research run ID

        Returns:
            ResearchRunState or None if not found
        """
        query = """
            SELECT run_id, state_data, version, last_event_id, updated_at, created_at
            FROM rp_research_run_state
            WHERE run_id = %s
        """

        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (run_id,))
                row = await cursor.fetchone()

        if not row:
            return None

        state_dict = dict(row["state_data"])
        state_dict["version"] = row["version"]

        # Hydrate timeline from rp_timeline_events (now returns proper TimelineEvent models)
        timeline_events = await self.get_timeline_events(run_id)
        state_dict["timeline"] = timeline_events

        return ResearchRunState(**state_dict)

    async def get_research_run_state_locked(
        self, run_id: str, conn: AsyncConnection[Any]
    ) -> Optional[ResearchRunState]:
        """
        Get current research run state with row-level lock (SELECT FOR UPDATE).

        This should be called within a transaction to hold the lock.
        Hydrates timeline from rp_timeline_events table as proper Pydantic models.

        Args:
            run_id: Research run ID
            conn: Database connection (within transaction)

        Returns:
            ResearchRunState or None if not found
        """
        query = """
            SELECT run_id, state_data, version, last_event_id, updated_at, created_at
            FROM rp_research_run_state
            WHERE run_id = %s
            FOR UPDATE
        """

        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, (run_id,))
            row = await cursor.fetchone()

        if not row:
            return None

        state_dict = dict(row["state_data"])
        state_dict["version"] = row["version"]

        # Hydrate timeline from rp_timeline_events (now returns proper TimelineEvent models)
        timeline_events = await self.get_timeline_events(run_id)
        state_dict["timeline"] = timeline_events

        return ResearchRunState(**state_dict)

    async def delete_research_run_state(self, run_id: str) -> None:
        """
        Delete research run state (for cleanup/testing).

        Args:
            run_id: Research run ID
        """
        query = "DELETE FROM rp_research_run_state WHERE run_id = %s"

        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, (run_id,))
                await conn.commit()

        logger.info("Deleted research run state: run=%s", run_id)
