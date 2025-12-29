"""Add missing run_id foreign keys for telemetry tables.

Revision ID: 0029
Revises: 0028
Create Date: 2025-12-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Attach run_id foreign keys and clean inconsistent data."""
    op.execute(
        sa.text(
            """
            UPDATE llm_token_usages AS ltu
            SET run_id = NULL
            WHERE run_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM research_pipeline_runs AS rpr
                  WHERE rpr.run_id = ltu.run_id
              );
            """
        )
    )

    op.execute(
        sa.text(
            """
            DELETE FROM rp_code_execution_events AS rce
            WHERE NOT EXISTS (
                SELECT 1
                FROM research_pipeline_runs AS rpr
                WHERE rpr.run_id = rce.run_id
            );
            """
        )
    )

    op.execute(
        sa.text(
            """
            DELETE FROM rp_stage_skip_windows AS rssw
            WHERE NOT EXISTS (
                SELECT 1
                FROM research_pipeline_runs AS rpr
                WHERE rpr.run_id = rssw.run_id
            );
            """
        )
    )

    op.create_foreign_key(
        constraint_name="llm_token_usages_run_id_fkey",
        source_table="llm_token_usages",
        referent_table="research_pipeline_runs",
        local_cols=["run_id"],
        remote_cols=["run_id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        constraint_name="fk_rp_code_execution_events_run",
        source_table="rp_code_execution_events",
        referent_table="research_pipeline_runs",
        local_cols=["run_id"],
        remote_cols=["run_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        constraint_name="fk_rp_stage_skip_windows_run",
        source_table="rp_stage_skip_windows",
        referent_table="research_pipeline_runs",
        local_cols=["run_id"],
        remote_cols=["run_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Drop run_id foreign keys."""
    op.drop_constraint(
        constraint_name="fk_rp_stage_skip_windows_run",
        table_name="rp_stage_skip_windows",
        type_="foreignkey",
    )
    op.drop_constraint(
        constraint_name="fk_rp_code_execution_events_run",
        table_name="rp_code_execution_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        constraint_name="llm_token_usages_run_id_fkey",
        table_name="llm_token_usages",
        type_="foreignkey",
    )
