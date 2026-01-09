"""Add supporting indexes for frequently queried columns.

Revision ID: 0030
Revises: 0029
Create Date: 2025-12-29
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create indexes for high-traffic WHERE clauses."""
    op.create_index(
        index_name="idx_chat_summaries_conversation_id",
        table_name="chat_summaries",
        columns=["conversation_id"],
    )
    op.create_index(
        index_name="idx_imported_conv_summaries_conversation_id",
        table_name="imported_conversation_summaries",
        columns=["conversation_id"],
    )
    op.create_index(
        index_name="idx_file_attachments_chat_message_id",
        table_name="file_attachments",
        columns=["chat_message_id"],
    )
    op.create_index(
        index_name="idx_ideas_conversation_id",
        table_name="ideas",
        columns=["conversation_id"],
    )
    op.create_index(
        index_name="idx_ideas_created_by_user_id",
        table_name="ideas",
        columns=["created_by_user_id"],
    )
    op.create_index(
        index_name="idx_idea_versions_idea_id",
        table_name="idea_versions",
        columns=["idea_id"],
    )
    op.create_index(
        index_name="idx_conversations_imported_by_user_id",
        table_name="conversations",
        columns=["imported_by_user_id"],
    )
    op.create_index(
        index_name="idx_conversations_status",
        table_name="conversations",
        columns=["status"],
    )
    op.create_index(
        index_name="idx_rp_runs_status",
        table_name="research_pipeline_runs",
        columns=["status"],
    )
    op.create_index(
        index_name="idx_llm_token_usages_run_id",
        table_name="llm_token_usages",
        columns=["run_id"],
    )


def downgrade() -> None:
    """Drop indexes created in upgrade."""
    op.drop_index(
        index_name="idx_llm_token_usages_run_id",
        table_name="llm_token_usages",
    )
    op.drop_index(
        index_name="idx_rp_runs_status",
        table_name="research_pipeline_runs",
    )
    op.drop_index(
        index_name="idx_conversations_status",
        table_name="conversations",
    )
    op.drop_index(
        index_name="idx_conversations_imported_by_user_id",
        table_name="conversations",
    )
    op.drop_index(
        index_name="idx_idea_versions_idea_id",
        table_name="idea_versions",
    )
    op.drop_index(
        index_name="idx_ideas_created_by_user_id",
        table_name="ideas",
    )
    op.drop_index(
        index_name="idx_ideas_conversation_id",
        table_name="ideas",
    )
    op.drop_index(
        index_name="idx_file_attachments_chat_message_id",
        table_name="file_attachments",
    )
    op.drop_index(
        index_name="idx_imported_conv_summaries_conversation_id",
        table_name="imported_conversation_summaries",
    )
    op.drop_index(
        index_name="idx_chat_summaries_conversation_id",
        table_name="chat_summaries",
    )
