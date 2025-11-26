"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2025-11-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("google_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="users_pkey"),
        sa.UniqueConstraint("email", name="users_email_key"),
        sa.UniqueConstraint("google_id", name="users_google_id_key"),
    )

    # Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "import_date",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("imported_chat", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("imported_by_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["imported_by_user_id"],
            ["users.id"],
            name="conversations_imported_by_user_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="conversations_pkey"),
    )
    op.create_index("idx_conversations_url", "conversations", ["url"])
    op.create_index(
        "idx_conversations_title_trgm",
        "conversations",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )

    # Create ideas table
    op.create_table(
        "ideas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("active_idea_version_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="ideas_conversation_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="ideas_created_by_user_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="ideas_pkey"),
    )

    # Create idea_versions table
    op.create_table(
        "idea_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("idea_id", sa.Integer(), nullable=False),
        sa.Column("is_manual_edit", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("short_hypothesis", sa.Text(), nullable=False),
        sa.Column("related_work", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("experiments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=False),
        sa.Column(
            "risk_factors_and_limitations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["idea_id"],
            ["ideas.id"],
            name="idea_versions_idea_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="idea_versions_created_by_user_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="idea_versions_pkey"),
    )

    # Add foreign key from ideas to idea_versions for active_idea_version_id
    op.create_foreign_key(
        "ideas_active_version_fk",
        "ideas",
        "idea_versions",
        ["active_idea_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("idea_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_by_user_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="chat_messages_role_check"),
        sa.ForeignKeyConstraint(
            ["idea_id"],
            ["ideas.id"],
            name="chat_messages_idea_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sent_by_user_id"],
            ["users.id"],
            name="chat_messages_sent_by_user_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="chat_messages_pkey"),
    )
    op.create_index(
        "unique_sequence_per_idea",
        "chat_messages",
        ["idea_id", "sequence_number"],
        unique=True,
    )

    # Create chat_summaries table
    op.create_table(
        "chat_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("latest_message_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="chat_summaries_conversation_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="chat_summaries_pkey"),
    )

    # Create imported_conversation_summaries table
    op.create_table(
        "imported_conversation_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="imported_conversation_summaries_conversation_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="imported_conversation_summaries_pkey"),
    )

    # Create conversation_memories table
    op.create_table(
        "conversation_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("memory_source", sa.Text(), nullable=False),
        sa.Column("memories", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="conversation_memories_conversation_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="conversation_memories_pkey"),
        sa.UniqueConstraint(
            "conversation_id",
            "memory_source",
            name="conversation_memories_conversation_id_memory_source_key",
        ),
    )

    # Create file_attachments table
    op.create_table(
        "file_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_message_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["chat_message_id"],
            ["chat_messages.id"],
            name="file_attachments_chat_message_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="file_attachments_conversation_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name="file_attachments_uploaded_by_user_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="file_attachments_pkey"),
    )
    op.create_index(
        "idx_file_attachments_conversation_id",
        "file_attachments",
        ["conversation_id"],
    )
    op.create_index("idx_file_attachments_file_type", "file_attachments", ["file_type"])

    # Create user_sessions table
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="user_sessions_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="user_sessions_pkey"),
        sa.UniqueConstraint("session_token", name="user_sessions_session_token_key"),
    )
    op.create_index("idx_user_sessions_token", "user_sessions", ["session_token"])
    op.create_index("idx_user_sessions_expires_at", "user_sessions", ["expires_at"])

    # Create service_keys table
    op.create_table(
        "service_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.Text(), nullable=False),
        sa.Column("api_key_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="service_keys_pkey"),
        sa.UniqueConstraint("service_name", name="service_keys_service_name_key"),
    )
    op.create_index("idx_service_keys_hash", "service_keys", ["api_key_hash"])

    # Create llm_prompts table
    op.create_table(
        "llm_prompts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prompt_type", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="llm_prompts_created_by_user_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="llm_prompts_pkey"),
    )
    # Create partial unique index for active prompts only
    op.execute(
        """
        CREATE UNIQUE INDEX unique_active_prompt 
        ON llm_prompts (prompt_type) 
        WHERE is_active = true
    """
    )

    # Create default_llm_parameters table
    op.create_table(
        "default_llm_parameters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prompt_type", sa.Text(), nullable=False),
        sa.Column("llm_provider", sa.Text(), nullable=False),
        sa.Column("llm_model", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="default_llm_parameters_created_by_user_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="default_llm_parameters_pkey"),
        sa.UniqueConstraint("prompt_type", name="default_llm_parameters_prompt_type_key"),
    )

    # Create conversation_dashboard_view
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


def downgrade() -> None:
    pass
