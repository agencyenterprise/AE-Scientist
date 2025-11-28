"""Add manual seed columns to conversations and refresh dashboard view.

Revision ID: 0003
Revises: 0002
Create Date: 2025-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add manual seed metadata to conversations and refresh dashboard view."""
    op.add_column("conversations", sa.Column("manual_title", sa.Text(), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("manual_hypothesis", sa.Text(), nullable=True),
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW conversation_dashboard_view AS
        SELECT
            c.id,
            c.url,
            c.title,
            c.import_date,
            c.created_at,
            c.updated_at,
            c.imported_by_user_id AS user_id,
            u.name AS user_name,
            u.email AS user_email,
            iv.title AS idea_title,
            iv.abstract AS idea_abstract,
            (
                SELECT cm.content
                FROM chat_messages cm
                WHERE cm.idea_id = i.id AND cm.role = 'user'
                ORDER BY cm.sequence_number DESC
                LIMIT 1
            ) AS last_user_message_content,
            (
                SELECT cm.content
                FROM chat_messages cm
                WHERE cm.idea_id = i.id AND cm.role = 'assistant'
                ORDER BY cm.sequence_number DESC
                LIMIT 1
            ) AS last_assistant_message_content,
            c.manual_title,
            c.manual_hypothesis
        FROM conversations c
        LEFT JOIN users u ON c.imported_by_user_id = u.id
        LEFT JOIN ideas i ON i.conversation_id = c.id
        LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id
        """
    )


def downgrade() -> None:
    """Revert manual seed metadata changes."""
    op.execute(
        """
        CREATE OR REPLACE VIEW conversation_dashboard_view AS
        SELECT
            c.id,
            c.url,
            c.title,
            c.import_date,
            c.created_at,
            c.updated_at,
            c.imported_by_user_id AS user_id,
            u.name AS user_name,
            u.email AS user_email,
            iv.title AS idea_title,
            iv.abstract AS idea_abstract,
            (
                SELECT cm.content
                FROM chat_messages cm
                WHERE cm.idea_id = i.id AND cm.role = 'user'
                ORDER BY cm.sequence_number DESC
                LIMIT 1
            ) AS last_user_message_content,
            (
                SELECT cm.content
                FROM chat_messages cm
                WHERE cm.idea_id = i.id AND cm.role = 'assistant'
                ORDER BY cm.sequence_number DESC
                LIMIT 1
            ) AS last_assistant_message_content
        FROM conversations c
        LEFT JOIN users u ON c.imported_by_user_id = u.id
        LEFT JOIN ideas i ON i.conversation_id = c.id
        LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id
        """
    )
    op.drop_column("conversations", "manual_hypothesis")
    op.drop_column("conversations", "manual_title")
