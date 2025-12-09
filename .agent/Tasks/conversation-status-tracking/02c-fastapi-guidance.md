# FastAPI & Pydantic Technical Guidance

## Agent
fastapi-expert

## Timestamp
2025-12-08 22:30 (Updated: 2025-12-09 INLINE-QUERIES)

---

## Project Analysis

### Detected Versions

| Package | Version | Notes |
|---------|---------|-------|
| fastapi | 0.116.1 | Modern async-first framework |
| pydantic | v2.x (via FastAPI 0.116.1) | BaseModel, Field, field_validator patterns |
| uvicorn | 0.35.0 | ASGI server |
| starlette | (implicit via FastAPI) | Underlying framework |
| psycopg2-binary | 2.9.9 | Database connectivity |
| alembic | 1.16.5 | Database migrations |

### Pydantic Version
**v2.x** - This project uses Pydantic v2 patterns. References in code confirm:
- `from pydantic import BaseModel, Field, field_validator` (line 11, conversations.py)
- Field usage with validation decorators
- No `Config` classes detected

### Key Configuration
- **Async database**: Yes - Uses psycopg2 with explicit cursor context managers
- **Authentication**: FastAPI middleware with `get_current_user`
- **OpenAPI**: Enabled with Field descriptions in all models
- **Transaction handling**: Explicit connection context + cursor management
- **Query Strategy**: Inline queries (no database views for this feature)

---

## Version-Specific Guidance

### Do's ✅

1. **Use Pydantic v2 Field syntax**
   ```python
   from pydantic import BaseModel, Field

   class ConversationResponse(BaseModel):
       status: str = Field(
           ...,
           description="Conversation status: 'draft' or 'with_research'"
       )
   ```

2. **Type hints in NamedTuple fields**
   - The codebase uses NamedTuple for DB data containers
   - Add status field with explicit type: `status: str`
   - Keep description in comments since NamedTuple lacks Field()

3. **String validation at migration/application level**
   - Define `CONVERSATION_STATUSES = ('draft', 'with_research')` constant
   - Validate in methods before database operations
   - Don't use PostgreSQL CHECK constraints (codebase pattern: validation via Python tuple)

4. **Transaction-safe cursor operations**
   - Follow pattern from research_pipeline_runs.py line 75-112
   - Use `with self._get_connection() as conn:` for transaction boundary
   - Use `with conn.cursor() as cursor:` for statement execution
   - Call `conn.commit()` after all operations complete
   - Create helper method `_update_conversation_status_with_cursor(cursor, ...)` for reuse in multi-step transactions

5. **Datetime handling in migrations**
   - Don't calculate defaults in migration code
   - Use `server_default=sa.text("...")` for database-side defaults
   - Handle null dates: `status='draft'` for all existing records during backfill

6. **Response model consistency**
   - Add status field to ConversationResponse Pydantic model
   - Update convert_db_to_api_response() function to map status
   - Keep ISO format for timestamps throughout

7. **Inline queries for dashboard data**
   - Service layer queries already SELECT all columns from conversations table
   - Status field will be automatically included in results
   - No database view changes needed - the status column is naturally available in all queries

### Don'ts ❌

1. **Don't use Pydantic v1 syntax**
   ```python
   # ❌ WRONG - v1 syntax
   class Config:
       orm_mode = True

   # ✅ CORRECT - v2 syntax (if needed, not for this feature)
   model_config = ConfigDict(from_attributes=True)
   ```

2. **Don't add database CHECK constraints**
   - Codebase validates status in Python via tuple constant
   - Maintains flexibility for future status values
   - Simpler migration and rollback logic

3. **Don't await database operations in sync functions**
   - psycopg2 is synchronous
   - Use explicit cursor context managers instead of async/await
   - Current implementation pattern works well

4. **Don't forget to backfill during migration**
   - Determine existing status based on research run presence
   - Set to 'with_research' if idea_id exists in research_pipeline_runs
   - Set to 'draft' otherwise

5. **Don't commit inside helper functions**
   - Keep commit at transaction boundary (in create_research_pipeline_run)
   - Helper methods should only execute SQL via cursor

6. **Don't update database views**
   - The status column is already part of conversations table
   - Inline queries in service layer naturally include all table columns
   - No view modifications needed for inline query approach

---

## Recommended Patterns for This Feature

### 1. Migration Pattern (SIMPLIFIED - No View Updates)

```python
# File: server/database_migrations/versions/0013_add_conversation_status.py

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add status column to conversations table with backfill logic."""
    # Step 1: Add column with server default
    op.add_column(
        "conversations",
        sa.Column(
            "status",
            sa.String(255),
            server_default="draft",
            nullable=False,
        ),
    )

    # Step 2: Backfill existing conversations based on research pipeline runs
    # Conversations with research runs get 'with_research', others get 'draft'
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE conversations c
        SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM research_pipeline_runs rpr
                JOIN ideas i ON rpr.idea_id = i.id
                WHERE i.conversation_id = c.id
                LIMIT 1
            ) THEN 'with_research'
            ELSE 'draft'
        END
        WHERE status = 'draft'
    """))
    conn.commit()


def downgrade() -> None:
    """Remove status column."""
    op.drop_column("conversations", "status")
```

### 2. NamedTuple Additions

```python
# File: server/app/services/database/conversations.py

class FullConversation(NamedTuple):
    """Detailed conversation response including all messages."""

    id: int
    url: str
    title: str
    import_date: str
    created_at: datetime
    updated_at: datetime
    has_images: Optional[bool]
    has_pdfs: Optional[bool]
    user_id: int
    user_name: str
    user_email: str
    imported_chat: Optional[List[ImportedChatMessage]]
    manual_title: Optional[str]
    manual_hypothesis: Optional[str]
    status: str  # NEW: Conversation status ('draft' or 'with_research')


class DashboardConversation(NamedTuple):
    """Conversation fields for dashboard list view."""

    id: int
    url: str
    title: str
    import_date: str
    created_at: datetime
    updated_at: datetime
    user_id: int
    user_name: str
    user_email: str
    idea_title: Optional[str]
    idea_abstract: Optional[str]
    last_user_message_content: Optional[str]
    last_assistant_message_content: Optional[str]
    manual_title: Optional[str]
    manual_hypothesis: Optional[str]
    status: str  # NEW: Conversation status from inline query
```

### 3. Pydantic Model Update

```python
# File: server/app/models/conversations.py

from pydantic import BaseModel, Field

class ConversationResponse(BaseModel):
    """Response model for conversation API endpoints."""

    id: int = Field(..., description="Database ID of the conversation")
    url: str = Field(..., description="Original conversation share URL")
    title: str = Field(..., description="Conversation title")
    import_date: str = Field(..., description="ISO format import timestamp")
    created_at: str = Field(..., description="ISO format creation timestamp")
    updated_at: str = Field(..., description="ISO format last update timestamp")
    has_images: Optional[bool] = Field(
        None, description="Whether conversation contains images"
    )
    has_pdfs: Optional[bool] = Field(
        None, description="Whether conversation contains PDFs"
    )
    user_id: int = Field(..., description="ID of the user who imported the conversation")
    user_name: str = Field(..., description="Name of the user who imported the conversation")
    user_email: str = Field(..., description="Email of the user who imported the conversation")
    status: str = Field(
        ...,
        description="Conversation status: 'draft' (initial) or 'with_research' (has research runs)"
    )  # NEW FIELD
    imported_chat: Optional[List[ImportedChatMessage]] = Field(
        None, description="Conversation messages (optional)"
    )
    manual_title: Optional[str] = Field(
        None,
        description="Manual title provided when the conversation originates from a manual seed",
    )
    manual_hypothesis: Optional[str] = Field(
        None,
        description="Manual hypothesis provided when the conversation originates from a manual seed",
    )
    research_runs: List[ResearchRunSummary] = Field(
        default_factory=list,
        description="Research pipeline runs associated with the conversation",
    )
```

### 4. Service Layer Methods

```python
# File: server/app/services/database/conversations.py

# Add this constant at module level
CONVERSATION_STATUSES = ('draft', 'with_research')


class ConversationsMixin(ConnectionProvider):
    """Database operations for conversations."""

    def update_conversation_status(
        self, conversation_id: int, status: str
    ) -> bool:
        """
        Update conversation status to 'with_research' after research run created.

        Args:
            conversation_id: ID of conversation to update
            status: New status value (validated against CONVERSATION_STATUSES)

        Returns:
            True if updated, False if not found

        Raises:
            ValueError: If status not in CONVERSATION_STATUSES
        """
        if status not in CONVERSATION_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {', '.join(CONVERSATION_STATUSES)}"
            )

        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE conversations
                    SET status = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (status, now, conversation_id),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)

    def _update_conversation_status_with_cursor(
        self, cursor: PsycopgCursor, conversation_id: int, status: str
    ) -> None:
        """
        Update conversation status within existing transaction (no commit).

        Used by create_research_pipeline_run to update status atomically
        with the run creation.

        Args:
            cursor: Active database cursor from outer transaction
            conversation_id: ID of conversation to update
            status: New status value (validated against CONVERSATION_STATUSES)

        Raises:
            ValueError: If status not in CONVERSATION_STATUSES
        """
        if status not in CONVERSATION_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {', '.join(CONVERSATION_STATUSES)}"
            )

        now = datetime.now()
        cursor.execute(
            """
            UPDATE conversations
            SET status = %s, updated_at = %s
            WHERE id = %s
            """,
            (status, now, conversation_id),
        )

    # Update existing methods to return status field
    def get_conversation_by_id(self, conversation_id: int) -> Optional[FullConversation]:
        """Get a conversation by its ID, including full content and file attachment flags."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT c.id, c.url, c.title, c.import_date, c.imported_chat,
                           c.created_at, c.updated_at, c.status,  -- ADD THIS
                           u.id as user_id, u.name as user_name, u.email as user_email,
                           EXISTS(...) as has_images,
                           EXISTS(...) as has_pdfs,
                           c.manual_title, c.manual_hypothesis
                    FROM conversations c
                    JOIN users u ON c.imported_by_user_id = u.id
                    WHERE c.id = %s
                    """,
                    (conversation_id,),
                )
                row = cursor.fetchone()

        if not row:
            return None

        # ... existing message parsing ...

        return FullConversation(
            id=row["id"],
            url=row["url"],
            title=row["title"],
            import_date=row["import_date"].isoformat(),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            has_images=row["has_images"],
            has_pdfs=row["has_pdfs"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            user_email=row["user_email"],
            imported_chat=content,
            manual_title=row.get("manual_title"),
            manual_hypothesis=row.get("manual_hypothesis"),
            status=row["status"],  # ADD THIS
        )

    def list_conversations(
        self, limit: int = 100, offset: int = 0, user_id: int | None = None
    ) -> List[DashboardConversation]:
        """List conversations for dashboard using inline queries (no view dependency)."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                query = """
                    SELECT
                        c.id, c.url, c.title, c.import_date, c.created_at, c.updated_at,
                        c.status,  -- ADD THIS - now from conversations table directly
                        u.id as user_id, u.name as user_name, u.email as user_email,
                        i.title as idea_title, iv.abstract as idea_abstract,
                        (SELECT content FROM conversation_messages
                         WHERE conversation_id = c.id AND role = 'user'
                         ORDER BY created_at DESC LIMIT 1) as last_user_message_content,
                        (SELECT content FROM conversation_messages
                         WHERE conversation_id = c.id AND role = 'assistant'
                         ORDER BY created_at DESC LIMIT 1) as last_assistant_message_content,
                        c.manual_title, c.manual_hypothesis
                    FROM conversations c
                    JOIN users u ON c.imported_by_user_id = u.id
                    LEFT JOIN ideas i ON c.id = i.conversation_id
                    LEFT JOIN idea_versions iv ON i.id = iv.idea_id AND iv.is_current = true
                """
                params: list = []
                if user_id is not None:
                    query += " WHERE u.id = %s"
                    params.append(user_id)
                query += " ORDER BY c.updated_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                cursor.execute(query, params)
                rows = cursor.fetchall()

        return [
            DashboardConversation(
                id=row["id"],
                url=row["url"],
                title=row["title"],
                import_date=row["import_date"].isoformat(),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                user_id=row["user_id"],
                user_name=row["user_name"],
                user_email=row["user_email"],
                idea_title=row.get("idea_title"),
                idea_abstract=row.get("idea_abstract"),
                last_user_message_content=row.get("last_user_message_content"),
                last_assistant_message_content=row.get("last_assistant_message_content"),
                manual_title=row.get("manual_title"),
                manual_hypothesis=row.get("manual_hypothesis"),
                status=row["status"],  # ADD THIS - naturally included in query result
            )
            for row in rows
        ]
```

### 5. Research Pipeline Runs - Transaction Pattern

```python
# File: server/app/services/database/research_pipeline_runs.py

class ResearchPipelineRunsMixin(ConnectionProvider):
    def create_research_pipeline_run(
        self,
        *,
        run_id: str,
        idea_id: int,
        idea_version_id: int,
        status: str,
        start_deadline_at: Optional[datetime],
        cost: float,
    ) -> int:
        """
        Create a research pipeline run and auto-update conversation status.

        Uses a single transaction to ensure atomicity:
        1. Create the run
        2. Create run event
        3. Update conversation status to 'with_research'

        All operations commit together for consistency.
        """
        if status not in PIPELINE_RUN_STATUSES:
            raise ValueError(f"Invalid status '{status}'")

        now = datetime.now(timezone.utc)
        deadline = start_deadline_at

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # Step 1: Create research pipeline run
                cursor.execute(
                    """
                    INSERT INTO research_pipeline_runs (
                        run_id,
                        idea_id,
                        idea_version_id,
                        status,
                        cost,
                        start_deadline_at,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (run_id, idea_id, idea_version_id, status, cost, deadline, now, now),
                )
                new_id_row = cursor.fetchone()
                if not new_id_row:
                    raise ValueError("Failed to create research pipeline run (missing id).")
                new_id = new_id_row[0]

                # Step 2: Create run event
                self._insert_run_event_with_cursor(
                    cursor=cursor,
                    run_id=run_id,
                    event_type="created",
                    metadata={
                        "status": status,
                        "idea_id": idea_id,
                        "idea_version_id": idea_version_id,
                        "cost": cost,
                        "start_deadline_at": deadline.isoformat() if deadline else None,
                    },
                    occurred_at=now,
                )

                # Step 3: Get conversation_id from idea and update its status
                # Get conversation_id from the idea we just created a run for
                cursor.execute(
                    "SELECT conversation_id FROM ideas WHERE id = %s",
                    (idea_id,),
                )
                idea_row = cursor.fetchone()
                if idea_row:
                    conversation_id = idea_row[0]
                    # Call the helper method to update status within this transaction
                    self._update_conversation_status_with_cursor(
                        cursor=cursor,
                        conversation_id=conversation_id,
                        status='with_research',
                    )

                # All operations in one transaction
                conn.commit()
                return int(new_id)
```

### 6. API Response Conversion

```python
# File: server/app/api/conversations.py

def convert_db_to_api_response(
    db_conversation: DBFullConversation,
    research_runs: Optional[List[ResearchRunSummary]] = None,
) -> ConversationResponse:
    """Convert NamedTuple DBFullConversation to Pydantic ConversationResponse for API responses."""
    return ConversationResponse(
        id=db_conversation.id,
        url=db_conversation.url,
        title=db_conversation.title,
        import_date=db_conversation.import_date,
        created_at=db_conversation.created_at.isoformat(),
        updated_at=db_conversation.updated_at.isoformat(),
        has_images=db_conversation.has_images,
        has_pdfs=db_conversation.has_pdfs,
        user_id=db_conversation.user_id,
        user_name=db_conversation.user_name,
        user_email=db_conversation.user_email,
        status=db_conversation.status,  # NEW: Map from DB NamedTuple
        imported_chat=(
            [
                ImportedChatMessage(
                    role=msg.role,
                    content=msg.content,
                )
                for msg in db_conversation.imported_chat
            ]
            if db_conversation.imported_chat
            else None
        ),
        manual_title=db_conversation.manual_title,
        manual_hypothesis=db_conversation.manual_hypothesis,
        research_runs=research_runs or [],
    )
```

---

## Database Column Specification

**Column**: `status`
**Table**: `conversations`
**Type**: `VARCHAR(255)`
**Default**: `'draft'`
**Nullable**: `FALSE`
**Validation**: Python-level via `CONVERSATION_STATUSES` tuple

**Why VARCHAR(255) not TEXT**:
- Better for indexing: VARCHAR with length constraint can be indexed more efficiently than TEXT
- Matches stored value length (max 12 chars: 'with_research')
- Allows future database optimization and query performance tuning
- No CHECK constraints in this codebase (validated in Python)
- Easier migrations when adding new statuses

**Indexing Benefits**:
- If future performance requirements demand indexed status queries, VARCHAR(255) is ready
- Text columns cannot be fully indexed in the same way
- Provides flexibility for adding composite indexes (e.g., `(user_id, status)`)
- PostgreSQL can create B-tree indexes on VARCHAR with length constraints more efficiently

---

## Inline Query Strategy

### Why Not a Database View?

This implementation uses **inline queries** instead of a database view because:

1. **Simpler Migration**: Just add the column, no view maintenance
2. **Natural Composition**: Status is now part of the conversations table, so all queries SELECT it automatically
3. **Flexibility**: Inline queries allow for filtering and joins specific to each use case
4. **Maintenance**: No view updates needed when schema changes
5. **Performance**: Direct table queries with targeted subqueries where needed

### Query Pattern for Dashboard Data

```sql
SELECT
    c.id, c.url, c.title, c.import_date, c.created_at, c.updated_at,
    c.status,  -- Status column from conversations table
    u.id as user_id, u.name as user_name, u.email as user_email,
    i.title as idea_title, iv.abstract as idea_abstract,
    (SELECT content FROM conversation_messages
     WHERE conversation_id = c.id AND role = 'user'
     ORDER BY created_at DESC LIMIT 1) as last_user_message_content,
    (SELECT content FROM conversation_messages
     WHERE conversation_id = c.id AND role = 'assistant'
     ORDER BY created_at DESC LIMIT 1) as last_assistant_message_content,
    c.manual_title, c.manual_hypothesis
FROM conversations c
JOIN users u ON c.imported_by_user_id = u.id
LEFT JOIN ideas i ON c.id = i.conversation_id
LEFT JOIN idea_versions iv ON i.id = iv.idea_id AND iv.is_current = true
ORDER BY c.updated_at DESC
```

---

## Transaction Patterns

### Single Operation (Update Status)
```python
# Simple update - automatic commit after context exit
with self._get_connection() as conn:
    with conn.cursor() as cursor:
        cursor.execute("UPDATE conversations SET status = %s WHERE id = %s", ...)
    conn.commit()
```

### Multi-Step Operation (Create Run + Update Status)
```python
# All operations in single transaction
with self._get_connection() as conn:
    with conn.cursor() as cursor:
        # Step 1: Insert
        cursor.execute("INSERT INTO ...", ...)

        # Step 2: Helper method executes without commit
        self._helper_method_with_cursor(cursor, ...)

        # Step 3: Final commit
        conn.commit()
```

---

## Error Handling Patterns

```python
# Validation before database operation
if status not in CONVERSATION_STATUSES:
    raise ValueError(
        f"Invalid status '{status}'. Must be one of: {', '.join(CONVERSATION_STATUSES)}"
    )

# Check result after operation
if not cursor.rowcount > 0:
    # Record not found
    return False

# Connection errors handled by ConnectionProvider base class
```

---

## Testing Considerations

1. **Unit tests** for status validation
   - `CONVERSATION_STATUSES` constant validation
   - `update_conversation_status()` with valid/invalid statuses

2. **Integration tests** for transaction atomicity
   - Create run + status update in single transaction
   - Verify status transitions correctly

3. **Database migration test**
   - Backfill logic correctly assigns 'with_research' to conversations with runs
   - No view refresh needed (using inline queries)

---

## Documentation References

- [FastAPI Path Parameters](https://fastapi.tiangolo.com/tutorial/path-params/)
- [FastAPI Query Parameters](https://fastapi.tiangolo.com/tutorial/query-params/)
- [Pydantic Field Documentation](https://docs.pydantic.dev/latest/concepts/models/#field-definitions)
- [PostgreSQL Character Types](https://www.postgresql.org/docs/current/datatype-character.html)
- [Alembic Operations Reference](https://alembic.sqlalchemy.org/en/latest/ops.html)

---

## For Executor

Key implementation points to follow:

1. **Migration (Step 1 - Must be first)**
   - Add `status VARCHAR(255) DEFAULT 'draft'` column
   - Backfill based on research_pipeline_runs join
   - No view updates needed - use inline queries instead

2. **NamedTuples (Step 2 - Before API models)**
   - Add `status: str` field to FullConversation
   - Add `status: str` field to DashboardConversation
   - Comments explain the field since NamedTuple has no Field()

3. **Pydantic Models (Step 3)**
   - Add `status: str = Field(...)` to ConversationResponse
   - Description mentions both enum values clearly

4. **Service Methods (Step 4)**
   - Add `CONVERSATION_STATUSES` constant at module level
   - `update_conversation_status()` public method with validation
   - `_update_conversation_status_with_cursor()` helper for transactions

5. **Inline Queries (Step 5)**
   - Update `list_conversations()` to include `c.status` in SELECT
   - Use subqueries for last message fields (no view dependency)
   - Update `get_conversation_by_id()` to SELECT status field

6. **API Conversion (Step 6)**
   - Update `convert_db_to_api_response()` to map status field

7. **Research Runs Integration (Step 7)**
   - Modify `create_research_pipeline_run()` to call status update
   - Use cursor helper method to stay in same transaction
   - Fetch conversation_id from ideas table

8. **Error Handling**
   - ValueError for invalid status values
   - Return False if conversation not found on update

---

## Migration Simplification Summary

**OLD APPROACH**: Add column + Update view
**NEW APPROACH**: Add column + Backfill + Use inline queries

This is simpler because:
- Migration only touches schema (ADD COLUMN + backfill)
- No view creation/maintenance overhead
- Service layer queries naturally include the status field
- Easier to test and maintain
- No hidden dependencies on view definitions

---

⏸️ **APPROVAL REQUIRED**

Please review the revised FastAPI guidance with inline query approach. Reply with:
- **"proceed"** or **"yes"** - Guidance is correct, continue to implementation
- **"modify: [your feedback]"** - I'll adjust the recommendations
- **"elaborate: [topic]"** - I'll provide more details on specific patterns
- **"stop"** - Pause here

Waiting for your approval...
