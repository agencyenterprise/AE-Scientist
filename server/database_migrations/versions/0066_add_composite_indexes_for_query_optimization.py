"""Add composite indexes for query optimization.

This migration adds composite indexes identified by analyzing all database queries
in the application, particularly the large frontend queries:

1. list_all_research_pipeline_runs() - the main research runs listing page
2. list_conversations() - the conversations listing page
3. Progress CTEs using DISTINCT ON patterns
4. Various correlated subqueries

Indexes added:
- rp_run_stage_progress_events(run_id, created_at DESC) - DISTINCT ON optimization
- rp_paper_generation_events(run_id, created_at DESC) - DISTINCT ON optimization
- research_pipeline_runs(created_at DESC) - ORDER BY pagination
- conversations(imported_by_user_id, updated_at DESC) - filter + ORDER BY
- chat_messages(idea_id, role, sequence_number DESC) - correlated subqueries
- research_pipeline_runs(idea_id, status) - EXISTS subquery optimization
- paper_reviews(status, created_at) - stale review cleanup query
- rp_code_execution_events(run_id, run_type, started_at DESC NULLS LAST) - DISTINCT ON

Revision ID: 0066
Revises: 0065
Create Date: 2025-02-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0066"
down_revision: Union[str, None] = "0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create composite indexes for query optimization."""

    # =========================================================================
    # HIGH PRIORITY: Progress CTE optimization (DISTINCT ON patterns)
    # Used by list_all_research_pipeline_runs() - the largest frontend query
    # =========================================================================

    # Index for: DISTINCT ON (run_id) ... ORDER BY run_id, created_at DESC
    # in the latest_progress CTE
    op.create_index(
        index_name="idx_rp_run_stage_progress_events_run_created",
        table_name="rp_run_stage_progress_events",
        columns=["run_id", sa.text("created_at DESC")],
    )

    # Same pattern for paper generation events in the UNION
    op.create_index(
        index_name="idx_rp_paper_generation_events_run_created",
        table_name="rp_paper_generation_events",
        columns=["run_id", sa.text("created_at DESC")],
    )

    # =========================================================================
    # HIGH PRIORITY: Pagination optimization
    # Used by list_all_research_pipeline_runs() ORDER BY created_at DESC
    # =========================================================================

    op.create_index(
        index_name="idx_research_pipeline_runs_created_at",
        table_name="research_pipeline_runs",
        columns=[sa.text("created_at DESC")],
    )

    # =========================================================================
    # HIGH PRIORITY: Conversations listing optimization
    # Used by list_conversations() with user filter + ORDER BY updated_at DESC
    # =========================================================================

    op.create_index(
        index_name="idx_conversations_user_updated",
        table_name="conversations",
        columns=["imported_by_user_id", sa.text("updated_at DESC")],
    )

    # =========================================================================
    # HIGH PRIORITY: Chat messages correlated subqueries
    # Used for fetching last user/assistant message per conversation
    # WHERE idea_id = ? AND role = ? ORDER BY sequence_number DESC LIMIT 1
    # =========================================================================

    op.create_index(
        index_name="idx_chat_messages_idea_role_seq",
        table_name="chat_messages",
        columns=["idea_id", "role", sa.text("sequence_number DESC")],
    )

    # =========================================================================
    # MEDIUM PRIORITY: Run status filter optimization
    # Used by EXISTS subquery when filtering conversations by run status
    # =========================================================================

    op.create_index(
        index_name="idx_research_pipeline_runs_idea_status",
        table_name="research_pipeline_runs",
        columns=["idea_id", "status"],
    )

    # =========================================================================
    # MEDIUM PRIORITY: Paper reviews cleanup query
    # Used by mark_stale_reviews_as_failed() on server startup
    # WHERE status IN (...) AND created_at < threshold
    # =========================================================================

    op.create_index(
        index_name="idx_paper_reviews_status_created",
        table_name="paper_reviews",
        columns=["status", "created_at"],
    )

    # =========================================================================
    # MEDIUM PRIORITY: Code execution DISTINCT ON optimization
    # Used by list_latest_code_execution_events_by_run_type()
    # DISTINCT ON (run_type) WHERE run_id = ? ORDER BY run_type, started_at DESC
    # =========================================================================

    op.create_index(
        index_name="idx_rp_code_execution_events_run_type_started",
        table_name="rp_code_execution_events",
        columns=["run_id", "run_type", sa.text("started_at DESC NULLS LAST")],
    )


def downgrade() -> None:
    """Drop indexes created in upgrade."""

    op.drop_index(
        index_name="idx_rp_code_execution_events_run_type_started",
        table_name="rp_code_execution_events",
    )
    op.drop_index(
        index_name="idx_paper_reviews_status_created",
        table_name="paper_reviews",
    )
    op.drop_index(
        index_name="idx_research_pipeline_runs_idea_status",
        table_name="research_pipeline_runs",
    )
    op.drop_index(
        index_name="idx_chat_messages_idea_role_seq",
        table_name="chat_messages",
    )
    op.drop_index(
        index_name="idx_conversations_user_updated",
        table_name="conversations",
    )
    op.drop_index(
        index_name="idx_research_pipeline_runs_created_at",
        table_name="research_pipeline_runs",
    )
    op.drop_index(
        index_name="idx_rp_paper_generation_events_run_created",
        table_name="rp_paper_generation_events",
    )
    op.drop_index(
        index_name="idx_rp_run_stage_progress_events_run_created",
        table_name="rp_run_stage_progress_events",
    )
