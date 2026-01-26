"""
Ideas database operations.

Handles CRUD operations for ideas and idea_versions tables.
"""

import logging
from datetime import datetime
from typing import List, NamedTuple, Optional

from psycopg.rows import dict_row

from .base import ConnectionProvider

logger = logging.getLogger(__name__)


class IdeaVersionData(NamedTuple):
    """Idea version data."""

    idea_id: int
    version_id: int
    conversation_id: int
    title: str
    idea_markdown: str
    is_manual_edit: bool
    version_number: int
    created_at: datetime


class IdeaData(NamedTuple):
    """Idea data with active version."""

    idea_id: int
    conversation_id: int
    version_id: int
    title: str
    idea_markdown: str
    version_number: int
    is_manual_edit: bool
    version_created_at: datetime
    created_at: datetime
    updated_at: datetime


class IdeaCreationFromRunParams(NamedTuple):
    """Parameters for creating an idea from a parent run."""

    conversation_id: int
    source_version_id: int
    created_by_user_id: int


class IdeasMixin(ConnectionProvider):  # pylint: disable=abstract-method
    """Database operations for ideas."""

    async def create_idea(
        self,
        conversation_id: int,
        title: str,
        idea_markdown: str,
        created_by_user_id: int,
    ) -> int:
        """Create a new idea with initial version. Returns idea_id."""
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO ideas (conversation_id, created_at, updated_at, created_by_user_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """,
                    (conversation_id, now, now, created_by_user_id),
                )
                idea_row = await cursor.fetchone()
                if not idea_row:
                    raise ValueError("Failed to create idea (missing id).")
                idea_id: int = int(idea_row[0])

                await cursor.execute(
                    """
                    INSERT INTO idea_versions
                    (idea_id, title, idea_markdown, is_manual_edit, version_number, created_at, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        idea_id,
                        title,
                        idea_markdown,
                        False,
                        1,
                        now,
                        created_by_user_id,
                    ),
                )
                version_row = await cursor.fetchone()
                if not version_row:
                    raise ValueError("Failed to create idea version (missing id).")
                version_id: int = int(version_row[0])

                await cursor.execute(
                    "UPDATE ideas SET active_idea_version_id = %s, updated_at = %s WHERE id = %s",
                    (version_id, now, idea_id),
                )

                return idea_id

    async def get_idea_by_conversation_id(self, conversation_id: int) -> Optional[IdeaData]:
        """Get idea with active version for a conversation."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        i.id as idea_id,
                        i.conversation_id,
                        iv.id as version_id,
                        iv.title,
                        iv.idea_markdown,
                        iv.version_number,
                        iv.is_manual_edit,
                        iv.created_at as version_created_at,
                        i.created_at,
                        i.updated_at
                    FROM ideas i
                    LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id
                    WHERE i.conversation_id = %s
                """,
                    (conversation_id,),
                )
                result = await cursor.fetchone()
        if result:
            return IdeaData(
                idea_id=result["idea_id"],
                conversation_id=result["conversation_id"],
                version_id=result["version_id"],
                title=result["title"],
                idea_markdown=result["idea_markdown"],
                version_number=result["version_number"],
                is_manual_edit=result["is_manual_edit"],
                version_created_at=result["version_created_at"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
            )
        return None

    async def update_idea_version(
        self,
        idea_id: int,
        version_id: int,
        title: str,
        idea_markdown: str,
        is_manual_edit: bool,
    ) -> bool:
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """UPDATE idea_versions SET
                       title = %s,
                       idea_markdown = %s,
                       is_manual_edit = %s
                       WHERE id = %s AND idea_id = %s""",
                    (
                        title,
                        idea_markdown,
                        is_manual_edit,
                        version_id,
                        idea_id,
                    ),
                )
                return bool(cursor.rowcount > 0)

    async def create_idea_version(
        self,
        idea_id: int,
        title: str,
        idea_markdown: str,
        is_manual_edit: bool,
        created_by_user_id: int,
    ) -> int:
        """Create a new version of an idea. Returns version_id."""
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COALESCE(MAX(version_number), 0) + 1 FROM idea_versions WHERE idea_id = %s",
                    (idea_id,),
                )
                next_version_row = await cursor.fetchone()
                if not next_version_row:
                    raise ValueError("Failed to fetch next idea version id.")
                next_version = int(next_version_row[0])

                await cursor.execute(
                    """
                    INSERT INTO idea_versions
                    (idea_id, title, idea_markdown, is_manual_edit, version_number, created_at, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        idea_id,
                        title,
                        idea_markdown,
                        is_manual_edit,
                        next_version,
                        now,
                        created_by_user_id,
                    ),
                )
                insert_version_row = await cursor.fetchone()
                if not insert_version_row:
                    raise ValueError("Failed to create idea version (missing id).")
                version_id: int = int(insert_version_row[0])

                await cursor.execute(
                    "UPDATE ideas SET active_idea_version_id = %s, updated_at = %s WHERE id = %s",
                    (version_id, now, idea_id),
                )

                return version_id

    async def get_idea_versions(self, idea_id: int) -> List[IdeaVersionData]:
        """Get all versions of an idea, ordered by version number desc."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        iv.idea_id,
                        i.conversation_id,
                        iv.id as version_id,
                        iv.title,
                        iv.idea_markdown,
                        iv.is_manual_edit,
                        iv.version_number,
                        iv.created_at
                    FROM idea_versions iv
                    JOIN ideas i ON iv.idea_id = i.id
                    WHERE idea_id = %s
                    ORDER BY version_number DESC
                """,
                    (idea_id,),
                )
                results = await cursor.fetchall()
        return [
            IdeaVersionData(
                idea_id=row["idea_id"],
                conversation_id=row["conversation_id"],
                version_id=row["version_id"],
                title=row["title"],
                idea_markdown=row["idea_markdown"],
                is_manual_edit=row["is_manual_edit"],
                version_number=row["version_number"],
                created_at=row["created_at"],
            )
            for row in results
        ]

    async def get_idea_version_by_id(self, version_id: int) -> Optional[IdeaVersionData]:
        """Get a single idea version by id."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        iv.idea_id,
                        i.conversation_id,
                        iv.id as version_id,
                        iv.title,
                        iv.idea_markdown,
                        iv.is_manual_edit,
                        iv.version_number,
                        iv.created_at
                    FROM idea_versions iv
                    JOIN ideas i ON iv.idea_id = i.id
                    WHERE iv.id = %s
                    """,
                    (version_id,),
                )
                row = await cursor.fetchone()
        if not row:
            return None
        return IdeaVersionData(
            idea_id=row["idea_id"],
            conversation_id=row["conversation_id"],
            version_id=row["version_id"],
            title=row["title"],
            idea_markdown=row["idea_markdown"],
            is_manual_edit=row["is_manual_edit"],
            version_number=row["version_number"],
            created_at=row["created_at"],
        )

    async def get_idea_by_id(self, idea_id: int) -> Optional[IdeaData]:
        """Get an idea with its active version by idea id."""
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        i.id as idea_id,
                        i.conversation_id,
                        iv.id as version_id,
                        iv.title,
                        iv.idea_markdown,
                        iv.version_number,
                        iv.is_manual_edit,
                        iv.created_at as version_created_at,
                        i.created_at,
                        i.updated_at
                    FROM ideas i
                    LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id
                    WHERE i.id = %s
                    """,
                    (idea_id,),
                )
                result = await cursor.fetchone()
        if result:
            return IdeaData(
                idea_id=result["idea_id"],
                conversation_id=result["conversation_id"],
                version_id=result["version_id"],
                title=result["title"],
                idea_markdown=result["idea_markdown"],
                version_number=result["version_number"],
                is_manual_edit=result["is_manual_edit"],
                version_created_at=result["version_created_at"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
            )
        return None

    async def set_active_idea_version(self, idea_id: int, version_id: int) -> bool:
        """Set a specific version as the active version for an idea."""
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE ideas SET active_idea_version_id = %s, updated_at = %s WHERE id = %s",
                    (version_id, now, idea_id),
                )
                return bool(cursor.rowcount > 0)

    async def recover_idea_version(
        self, idea_id: int, source_version_id: int, created_by_user_id: int
    ) -> Optional[int]:
        """Create a new version by copying data from an existing version.

        This is used when "recovering" an older version - instead of just reactivating
        the old version, we create a new version with the same content to preserve history.

        Returns the new version ID if successful, None otherwise.
        """
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """SELECT title, idea_markdown, is_manual_edit
                       FROM idea_versions
                       WHERE id = %s AND idea_id = %s""",
                    (source_version_id, idea_id),
                )
                source_version = await cursor.fetchone()

                if not source_version:
                    return None

                title, idea_markdown, is_manual_edit = source_version

                await cursor.execute(
                    "SELECT COALESCE(MAX(version_number), 0) + 1 FROM idea_versions WHERE idea_id = %s",
                    (idea_id,),
                )
                next_version_row = await cursor.fetchone()
                if not next_version_row:
                    raise ValueError("Failed to compute next version number.")
                next_version_number = int(next_version_row[0])

                await cursor.execute(
                    """INSERT INTO idea_versions
                       (idea_id, title, idea_markdown, is_manual_edit, version_number, created_at, created_by_user_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (
                        idea_id,
                        title,
                        idea_markdown,
                        is_manual_edit,
                        next_version_number,
                        now,
                        created_by_user_id,
                    ),
                )
                new_version_row = await cursor.fetchone()
                if not new_version_row:
                    raise ValueError("Failed to duplicate idea version (missing id).")
                new_version_id: int = int(new_version_row[0])

                await cursor.execute(
                    "UPDATE ideas SET active_idea_version_id = %s, updated_at = %s WHERE id = %s",
                    (new_version_id, now, idea_id),
                )

                return new_version_id

    async def create_idea_from_run(
        self,
        params: IdeaCreationFromRunParams,
    ) -> int:
        """Create a new idea by copying data from an existing idea version.

        This is used when seeding a new idea from a completed research run.
        The new idea preserves all content from the source version but is
        linked to a new conversation.

        Args:
            params: IdeaCreationFromRunParams with all required fields

        Returns:
            The new idea_id

        Raises:
            ValueError: If source version not found or conversation already has an idea
        """
        now = datetime.now()
        async with self.aget_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cursor:
                # Check if conversation already has an idea
                await cursor.execute(
                    "SELECT id FROM ideas WHERE conversation_id = %s",
                    (params.conversation_id,),
                )
                existing = await cursor.fetchone()
                if existing:
                    raise ValueError(f"Conversation {params.conversation_id} already has an idea")

                # Fetch source version data
                await cursor.execute(
                    """SELECT title, idea_markdown
                       FROM idea_versions
                       WHERE id = %s""",
                    (params.source_version_id,),
                )
                source_row = await cursor.fetchone()

                if not source_row:
                    raise ValueError(f"Source idea version {params.source_version_id} not found")

                # Create new idea
                await cursor.execute(
                    """
                    INSERT INTO ideas (
                        conversation_id,
                        created_at,
                        updated_at,
                        created_by_user_id
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        params.conversation_id,
                        now,
                        now,
                        params.created_by_user_id,
                    ),
                )
                idea_row = await cursor.fetchone()
                if not idea_row:
                    raise ValueError("Failed to create idea (missing id).")
                idea_id: int = int(idea_row["id"])

                # Create initial version from source data
                await cursor.execute(
                    """
                    INSERT INTO idea_versions (
                        idea_id,
                        title,
                        idea_markdown,
                        is_manual_edit,
                        version_number,
                        created_at,
                        created_by_user_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        idea_id,
                        source_row["title"],
                        source_row["idea_markdown"],
                        False,
                        1,
                        now,
                        params.created_by_user_id,
                    ),
                )
                version_row = await cursor.fetchone()
                if not version_row:
                    raise ValueError("Failed to create idea version (missing id).")
                version_id: int = int(version_row["id"])

                # Set active version
                await cursor.execute(
                    "UPDATE ideas SET active_idea_version_id = %s, updated_at = %s WHERE id = %s",
                    (version_id, now, idea_id),
                )

                return idea_id
