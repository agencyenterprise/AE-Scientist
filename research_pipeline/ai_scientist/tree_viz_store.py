"""
Persist tree visualization payloads from the research pipeline.
"""

import logging
from dataclasses import dataclass
from typing import Any

import psycopg2
import psycopg2.extras

from ai_scientist.telemetry.event_persistence import _parse_database_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TreeVizStore:
    database_url: str

    def upsert(
        self,
        *,
        run_id: str,
        stage_id: str,
        viz: dict[str, Any],
        version: int,
    ) -> int:
        """
        Insert or update a tree visualization payload for a given run/stage.

        Returns the stored rp_tree_viz.id.
        """
        pg_config = _parse_database_url(self.database_url)
        upsert_query = """
            INSERT INTO rp_tree_viz (run_id, stage_id, viz, version)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (run_id, stage_id)
            DO UPDATE SET
                viz = EXCLUDED.viz,
                version = EXCLUDED.version,
                updated_at = now()
            RETURNING id
        """
        event_query = """
            INSERT INTO research_pipeline_run_events (run_id, event_type, metadata, occurred_at)
            VALUES (%s, %s, %s, now())
        """
        try:
            with psycopg2.connect(**pg_config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        upsert_query, (run_id, stage_id, psycopg2.extras.Json(viz), version)
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise RuntimeError("No id returned when upserting rp_tree_viz")
                    tree_viz_id = int(row[0])
                    cursor.execute(
                        event_query,
                        (
                            run_id,
                            "tree_viz_stored",
                            psycopg2.extras.Json(
                                {
                                    "stage_id": stage_id,
                                    "tree_viz_id": tree_viz_id,
                                    "version": version,
                                }
                            ),
                        ),
                    )
                conn.commit()
            return tree_viz_id
        except Exception:
            logger.exception(
                "Failed to upsert tree viz for run_id=%s stage_id=%s", run_id, stage_id
            )
            raise
