"""
Ideas database operations.

Handles CRUD operations for ideas and idea_versions tables.
"""

import json
import logging
from datetime import datetime
from typing import List, NamedTuple, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class IdeaVersionData(NamedTuple):
    """Idea version data."""

    version_id: int
    title: str
    short_hypothesis: str
    related_work: str
    abstract: str
    experiments: List[str]
    expected_outcome: str
    risk_factors_and_limitations: List[str]
    is_manual_edit: bool
    version_number: int
    created_at: datetime


class IdeaData(NamedTuple):
    """Idea data with active version."""

    idea_id: int
    conversation_id: int
    version_id: int
    title: str
    short_hypothesis: str
    related_work: str
    abstract: str
    experiments: List[str]
    expected_outcome: str
    risk_factors_and_limitations: List[str]
    version_number: int
    is_manual_edit: bool
    version_created_at: datetime
    created_at: datetime
    updated_at: datetime


class IdeasMixin:
    """Database operations for ideas."""

    def create_idea(
        self,
        conversation_id: int,
        title: str,
        short_hypothesis: str,
        related_work: str,
        abstract: str,
        experiments: List[str],
        expected_outcome: str,
        risk_factors_and_limitations: List[str],
        created_by_user_id: int,
    ) -> int:
        """Create a new idea with initial version. Returns idea_id."""
        now = datetime.now()
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore
            with conn.cursor() as cursor:
                # Create idea
                cursor.execute(
                    """
                    INSERT INTO ideas (conversation_id, created_at, updated_at, created_by_user_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """,
                    (conversation_id, now, now, created_by_user_id),
                )
                idea_id: int = cursor.fetchone()[0]

                # Create initial version
                cursor.execute(
                    """
                    INSERT INTO idea_versions
                    (idea_id, title, short_hypothesis, related_work, abstract, experiments, expected_outcome, risk_factors_and_limitations, is_manual_edit, version_number, created_at, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        idea_id,
                        title,
                        short_hypothesis,
                        related_work,
                        abstract,
                        json.dumps(experiments),
                        expected_outcome,
                        json.dumps(risk_factors_and_limitations),
                        False,
                        1,
                        now,
                        created_by_user_id,
                    ),
                )
                version_id: int = cursor.fetchone()[0]

                # Set as active version
                cursor.execute(
                    "UPDATE ideas SET active_idea_version_id = %s, updated_at = %s WHERE id = %s",
                    (version_id, now, idea_id),
                )

                conn.commit()
                return idea_id

    def get_idea_by_conversation_id(self, conversation_id: int) -> Optional[IdeaData]:
        """Get idea with active version for a conversation."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        i.id as idea_id,
                        i.conversation_id,
                        iv.id as version_id,
                        iv.title,
                        iv.short_hypothesis,
                        iv.related_work,
                        iv.abstract,
                        iv.experiments,
                        iv.expected_outcome,
                        iv.risk_factors_and_limitations,
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
                result = cursor.fetchone()
                if result:
                    return IdeaData(
                        idea_id=result["idea_id"],
                        conversation_id=result["conversation_id"],
                        version_id=result["version_id"],
                        title=result["title"],
                        short_hypothesis=result["short_hypothesis"],
                        related_work=result["related_work"],
                        abstract=result["abstract"],
                        experiments=result["experiments"],
                        expected_outcome=result["expected_outcome"],
                        risk_factors_and_limitations=result["risk_factors_and_limitations"],
                        version_number=result["version_number"],
                        is_manual_edit=result["is_manual_edit"],
                        version_created_at=result["version_created_at"],
                        created_at=result["created_at"],
                        updated_at=result["updated_at"],
                    )
                return None

    def update_idea_version(
        self,
        idea_id: int,
        version_id: int,
        title: str,
        short_hypothesis: str,
        related_work: str,
        abstract: str,
        experiments: List[str],
        expected_outcome: str,
        risk_factors_and_limitations: List[str],
        is_manual_edit: bool,
    ) -> bool:
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE idea_versions SET 
                       title = %s, 
                       short_hypothesis = %s, 
                       related_work = %s, 
                       abstract = %s, 
                       experiments = %s, 
                       expected_outcome = %s, 
                       risk_factors_and_limitations = %s, 
                       is_manual_edit = %s 
                       WHERE id = %s AND idea_id = %s""",
                    (
                        title,
                        short_hypothesis,
                        related_work,
                        abstract,
                        json.dumps(experiments),
                        expected_outcome,
                        json.dumps(risk_factors_and_limitations),
                        is_manual_edit,
                        version_id,
                        idea_id,
                    ),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)

    def create_idea_version(
        self,
        idea_id: int,
        title: str,
        short_hypothesis: str,
        related_work: str,
        abstract: str,
        experiments: List[str],
        expected_outcome: str,
        risk_factors_and_limitations: List[str],
        is_manual_edit: bool,
        created_by_user_id: int,
    ) -> int:
        """Create a new version of an idea. Returns version_id."""
        now = datetime.now()
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore
            with conn.cursor() as cursor:
                # Get next version number
                cursor.execute(
                    "SELECT COALESCE(MAX(version_number), 0) + 1 FROM idea_versions WHERE idea_id = %s",
                    (idea_id,),
                )
                next_version = cursor.fetchone()[0]

                # Create new version
                cursor.execute(
                    """
                    INSERT INTO idea_versions
                    (idea_id, title, short_hypothesis, related_work, abstract, experiments, expected_outcome, risk_factors_and_limitations, is_manual_edit, version_number, created_at, created_by_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        idea_id,
                        title,
                        short_hypothesis,
                        related_work,
                        abstract,
                        json.dumps(experiments),
                        expected_outcome,
                        json.dumps(risk_factors_and_limitations),
                        is_manual_edit,
                        next_version,
                        now,
                        created_by_user_id,
                    ),
                )
                version_id: int = cursor.fetchone()[0]

                # Update active version and idea timestamp
                cursor.execute(
                    "UPDATE ideas SET active_idea_version_id = %s, updated_at = %s WHERE id = %s",
                    (version_id, now, idea_id),
                )

                conn.commit()
                return version_id

    def get_idea_versions(self, idea_id: int) -> List[IdeaVersionData]:
        """Get all versions of an idea, ordered by version number desc."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id as version_id,
                        title,
                        short_hypothesis,
                        related_work,
                        abstract,
                        experiments,
                        expected_outcome,
                        risk_factors_and_limitations,
                        is_manual_edit,
                        version_number,
                        created_at
                    FROM idea_versions
                    WHERE idea_id = %s
                    ORDER BY version_number DESC
                """,
                    (idea_id,),
                )
                results = cursor.fetchall()
                return [
                    IdeaVersionData(
                        version_id=row["version_id"],
                        title=row["title"],
                        short_hypothesis=row["short_hypothesis"],
                        related_work=row["related_work"],
                        abstract=row["abstract"],
                        experiments=row["experiments"],
                        expected_outcome=row["expected_outcome"],
                        risk_factors_and_limitations=row["risk_factors_and_limitations"],
                        is_manual_edit=row["is_manual_edit"],
                        version_number=row["version_number"],
                        created_at=row["created_at"],
                    )
                    for row in results
                ]

    def get_idea_by_id(self, idea_id: int) -> Optional[IdeaData]:
        """Get an idea with its active version by idea id."""
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        i.id as idea_id,
                        i.conversation_id,
                        iv.id as version_id,
                        iv.title,
                        iv.short_hypothesis,
                        iv.related_work,
                        iv.abstract,
                        iv.experiments,
                        iv.expected_outcome,
                        iv.risk_factors_and_limitations,
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
                result = cursor.fetchone()
                if result:
                    return IdeaData(
                        idea_id=result["idea_id"],
                        conversation_id=result["conversation_id"],
                        version_id=result["version_id"],
                        title=result["title"],
                        short_hypothesis=result["short_hypothesis"],
                        related_work=result["related_work"],
                        abstract=result["abstract"],
                        experiments=result["experiments"],
                        expected_outcome=result["expected_outcome"],
                        risk_factors_and_limitations=result["risk_factors_and_limitations"],
                        version_number=result["version_number"],
                        is_manual_edit=result["is_manual_edit"],
                        version_created_at=result["version_created_at"],
                        created_at=result["created_at"],
                        updated_at=result["updated_at"],
                    )
                return None

    def set_active_idea_version(self, idea_id: int, version_id: int) -> bool:
        """Set a specific version as the active version for an idea."""
        now = datetime.now()
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE ideas SET active_idea_version_id = %s, updated_at = %s WHERE id = %s",
                    (version_id, now, idea_id),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)

    def recover_idea_version(
        self, idea_id: int, source_version_id: int, created_by_user_id: int
    ) -> Optional[int]:
        """Create a new version by copying data from an existing version.

        This is used when "recovering" an older version - instead of just reactivating
        the old version, we create a new version with the same content to preserve history.

        Returns the new version ID if successful, None otherwise.
        """
        now = datetime.now()
        with psycopg2.connect(**self.pg_config) as conn:  # type: ignore
            with conn.cursor() as cursor:
                # Get the source version data
                cursor.execute(
                    """SELECT title, short_hypothesis, related_work, abstract, experiments, expected_outcome, risk_factors_and_limitations, is_manual_edit
                       FROM idea_versions
                       WHERE id = %s AND idea_id = %s""",
                    (source_version_id, idea_id),
                )
                source_version = cursor.fetchone()

                if not source_version:
                    return None

                (
                    title,
                    short_hypothesis,
                    related_work,
                    abstract,
                    experiments,
                    expected_outcome,
                    risk_factors_and_limitations,
                    is_manual_edit,
                ) = source_version

                # Get the next version number
                cursor.execute(
                    "SELECT COALESCE(MAX(version_number), 0) + 1 FROM idea_versions WHERE idea_id = %s",
                    (idea_id,),
                )
                next_version_number = cursor.fetchone()[0]

                # Create the new version with copied data
                cursor.execute(
                    """INSERT INTO idea_versions
                       (idea_id, title, short_hypothesis, related_work, abstract, experiments, expected_outcome, risk_factors_and_limitations, is_manual_edit, version_number, created_at, created_by_user_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (
                        idea_id,
                        title,
                        short_hypothesis,
                        related_work,
                        abstract,
                        experiments,
                        expected_outcome,
                        risk_factors_and_limitations,
                        is_manual_edit,
                        next_version_number,
                        now,
                        created_by_user_id,
                    ),
                )
                new_version_id: int = cursor.fetchone()[0]

                # Set this new version as the active version
                cursor.execute(
                    "UPDATE ideas SET active_idea_version_id = %s, updated_at = %s WHERE id = %s",
                    (new_version_id, now, idea_id),
                )

                conn.commit()
                return new_version_id
