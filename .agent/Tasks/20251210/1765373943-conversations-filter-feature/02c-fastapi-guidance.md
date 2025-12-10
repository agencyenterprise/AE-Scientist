# FastAPI Technical Guidance: Conversations Filtering Feature

## Agent
fastapi-expert

## Timestamp
2025-12-10 07:45

---

## Project Analysis

### Detected Versions
| Package | Version | Notes |
|---------|---------|-------|
| fastapi | 0.116.1 | Latest stable, excellent Pydantic v2 support |
| pydantic | (implicit) | v2 (FastAPI 0.116+ defaults to v2) |
| uvicorn | 0.35.0 | Modern async server |
| starlette | (inherited) | Underlying framework via FastAPI |
| sqlalchemy | (via langchain) | Used indirectly through database layer |

### Pydantic Version
**v2 (implicit)** - FastAPI 0.116.1 requires Pydantic v2. All code must use v2 syntax.

### Current Architecture
- **Database Layer**: Direct `psycopg2` with `RealDictCursor` (NOT SQLAlchemy ORM)
- **API Pattern**: Function-based route handlers with async/await
- **Authentication**: Custom `get_current_user` dependency (works with FastAPI's Depends)
- **Type Hints**: Modern Python 3.12 union syntax (`str | None`)
- **Response Models**: Pydantic BaseModel classes for API responses

### Key Configuration
- Async: Yes (all endpoints are async)
- Direct SQL queries: Yes (raw psycopg2)
- Authentication: Custom user dependency
- OpenAPI: Enabled by default
- Type hints: Strong (mypy strict mode enabled)

---

## Feature Context

### What We're Building
Add server-side query parameter filtering to `GET /conversations`:
- Optional `conversation_status` parameter: `"draft"` or `"with_research"`
- Optional `run_status` parameter: `"pending"`, `"running"`, `"completed"`, or `"failed"`
- Both parameters independently optional; can be combined with AND logic
- Server-side validation against known status constants
- Dynamic SQL WHERE clauses based on provided filters

### Existing Pattern (Current Implementation)

**Current Endpoint (line 943-986 of conversations.py):**
```python
@router.get("")
async def list_conversations(
    request: Request, response: Response, limit: int = 100, offset: int = 0
) -> Union[ConversationListResponse, ErrorResponse]:
```

**Current Database Method (line 255-325 of conversations.py):**
```python
def list_conversations(
    self, limit: int = 100, offset: int = 0, user_id: int | None = None
) -> List[DashboardConversation]:
    """List conversations for dashboard with inline query and pagination."""
    # Builds dynamic WHERE clause based on parameters
    # Uses raw SQL with parameterized queries for security
```

---

## Version-Specific Guidance for FastAPI 0.116 + Pydantic v2

### Do's ✅

1. **Use Optional[str] or `str | None` for query parameters**
   - Both syntaxes work in Python 3.12, modern union syntax preferred
   - FastAPI automatically handles `None` as "not provided"
   - No need for `Query()` unless you need additional metadata

   ```python
   # GOOD: Simple optional query param
   async def list_conversations(
       conversation_status: str | None = None,
       run_status: str | None = None,
   ) -> ConversationListResponse:
       pass
   ```

2. **Validate against status constants EARLY**
   - Validate in the endpoint before passing to database layer
   - Use explicit constants defined in database module
   - Provide clear error messages

   ```python
   # GOOD: Early validation
   from app.services.database.conversations import CONVERSATION_STATUSES
   from app.services.database.research_pipeline_runs import PIPELINE_RUN_STATUSES

   if conversation_status is not None and conversation_status not in CONVERSATION_STATUSES:
       response.status_code = 400
       return ErrorResponse(
           error="Invalid conversation_status",
           detail=f"Must be one of: {', '.join(CONVERSATION_STATUSES)}"
       )
   ```

3. **Pass filters to database layer explicitly**
   - Keep endpoint responsible for validation, DB for queries
   - Update method signature to accept filter parameters
   - Let database layer build dynamic WHERE clauses

   ```python
   # GOOD: Clean separation of concerns
   conversations: List[DBDashboardConversation] = db.list_conversations(
       limit=limit,
       offset=offset,
       user_id=user.id,
       conversation_status=conversation_status,  # NEW
       run_status=run_status,                     # NEW
   )
   ```

4. **Build SQL WHERE clauses dynamically in database layer**
   - Use parameterized queries (already done with `%s` placeholders)
   - Add conditional JOINs only when needed
   - Add DISTINCT when JOINing with runs table

   ```python
   # GOOD: Dynamic SQL in database layer
   query = """
       SELECT DISTINCT c.*, ...
       FROM conversations c
       LEFT JOIN users u ON c.imported_by_user_id = u.id
       LEFT JOIN ideas i ON i.conversation_id = c.id
       LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id
   """

   params: list = []

   if user_id is not None:
       query += " WHERE c.imported_by_user_id = %s"
       params.append(user_id)

   # Add more WHERE conditions only when needed
   if conversation_status is not None:
       if "WHERE" in query:
           query += " AND c.status = %s"
       else:
           query += " WHERE c.status = %s"
       params.append(conversation_status)

   if run_status is not None:
       # Add JOIN for runs table if not already present
       if "research_pipeline_runs" not in query:
           query = query.replace(
               "LEFT JOIN idea_versions",
               "LEFT JOIN research_pipeline_runs rpr ON rpr.idea_id = i.id\n" +
               "LEFT JOIN idea_versions"
           )
       if "WHERE" in query:
           query += " AND rpr.status = %s"
       else:
           query += " WHERE rpr.status = %s"
       params.append(run_status)

   query += " ORDER BY c.updated_at DESC LIMIT %s OFFSET %s"
   params.extend([limit, offset])
   ```

5. **Use type hints for all query parameters**
   - FastAPI uses type hints for OpenAPI documentation
   - Helps IDE autocomplete and type checking
   - Makes endpoint contract explicit

   ```python
   # GOOD: Complete type hints
   @router.get("")
   async def list_conversations(
       request: Request,
       response: Response,
       limit: int = 100,
       offset: int = 0,
       conversation_status: str | None = None,  # NEW
       run_status: str | None = None,            # NEW
   ) -> Union[ConversationListResponse, ErrorResponse]:
   ```

6. **Keep validation logic readable**
   - Use helper functions for complex validation
   - Document why validation matters (e.g., "prevents SQL injection")
   - Return specific error messages for each validation failure

   ```python
   # GOOD: Separate validation helper
   def _validate_filters(
       conversation_status: str | None,
       run_status: str | None,
       response: Response
   ) -> Union[None, ErrorResponse]:
       """Validate filter parameters against known values."""
       if conversation_status and conversation_status not in CONVERSATION_STATUSES:
           response.status_code = 400
           return ErrorResponse(
               error="Invalid conversation_status",
               detail=f"Must be one of: {', '.join(CONVERSATION_STATUSES)}"
           )

       if run_status and run_status not in PIPELINE_RUN_STATUSES:
           response.status_code = 400
           return ErrorResponse(
               error="Invalid run_status",
               detail=f"Must be one of: {', '.join(PIPELINE_RUN_STATUSES)}"
           )

       return None
   ```

### Don'ts ❌

1. **Don't use Pydantic v1 Config patterns**
   ```python
   # BAD: Pydantic v1 syntax
   class Model(BaseModel):
       class Config:
           orm_mode = True  # WRONG for v2

   # GOOD: Pydantic v2 syntax
   class Model(BaseModel):
       model_config = ConfigDict(from_attributes=True)
   ```

2. **Don't validate at the database layer - validate at endpoint**
   ```python
   # BAD: Validation in database layer
   def list_conversations(self, status: str):
       if status not in STATUSES:
           raise ValueError(...)  # Wrong place

   # GOOD: Validate before passing to database
   if conversation_status not in CONVERSATION_STATUSES:
       return ErrorResponse(...)  # At endpoint level

   db.list_conversations(status=conversation_status)  # Already validated
   ```

3. **Don't use optional filtering without defaults**
   ```python
   # BAD: No default means parameter is required
   async def list_conversations(
       conversation_status: str  # REQUIRED!
   ):
       pass

   # GOOD: Optional with None default
   async def list_conversations(
       conversation_status: str | None = None
   ):
       pass
   ```

4. **Don't add unnecessary Query() wrapper for simple strings**
   ```python
   # UNNECESSARY: Query() only needed for advanced validation
   from fastapi import Query

   async def list_conversations(
       conversation_status: str | None = Query(None)  # Overkill
   ):
       pass

   # GOOD: Simple optional parameter
   async def list_conversations(
       conversation_status: str | None = None  # Perfect
   ):
       pass
   ```

5. **Don't build dynamic SQL without parameterization**
   ```python
   # BAD: SQL injection risk!
   query = f"WHERE status = '{status}'"  # NEVER do this

   # GOOD: Always use parameterized queries
   query = "WHERE status = %s"
   params.append(status)
   cursor.execute(query, params)
   ```

6. **Don't forget DISTINCT when JOINing with one-to-many tables**
   ```python
   # BAD: Returns duplicate conversations if multiple runs exist
   SELECT c.* FROM conversations c
   LEFT JOIN research_pipeline_runs r ON c.id = r.conversation_id

   # GOOD: DISTINCT eliminates duplicates
   SELECT DISTINCT c.* FROM conversations c
   LEFT JOIN research_pipeline_runs r ON c.id = r.conversation_id
   ```

---

## Recommended Patterns for This Feature

### Pattern 1: Query Parameter Validation

**Location:** `server/app/api/conversations.py` endpoint

```python
from typing import Union
from fastapi import APIRouter, Request, Response
from app.models import ConversationListResponse, ErrorResponse
from app.services.database.conversations import CONVERSATION_STATUSES
from app.services.database.research_pipeline_runs import PIPELINE_RUN_STATUSES
from app.middleware.auth import get_current_user
from app.services import get_database

router = APIRouter(prefix="/conversations")

@router.get("")
async def list_conversations(
    request: Request,
    response: Response,
    limit: int = 100,
    offset: int = 0,
    conversation_status: str | None = None,
    run_status: str | None = None,
) -> Union[ConversationListResponse, ErrorResponse]:
    """
    Get a paginated list of conversations for the current user.

    Query Parameters:
    - conversation_status: Filter by "draft" or "with_research" (optional)
    - run_status: Filter by "pending", "running", "completed", or "failed" (optional)
    """
    user = get_current_user(request)

    # Validate limit and offset (existing logic)
    if limit <= 0 or limit > 1000:
        response.status_code = 400
        return ErrorResponse(error="Invalid limit", detail="Limit must be between 1 and 1000")

    if offset < 0:
        response.status_code = 400
        return ErrorResponse(error="Invalid offset", detail="Offset must be non-negative")

    # Validate conversation_status
    if conversation_status is not None and conversation_status not in CONVERSATION_STATUSES:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid conversation_status",
            detail=f"Must be one of: {', '.join(CONVERSATION_STATUSES)}"
        )

    # Validate run_status
    if run_status is not None and run_status not in PIPELINE_RUN_STATUSES:
        response.status_code = 400
        return ErrorResponse(
            error="Invalid run_status",
            detail=f"Must be one of: {', '.join(PIPELINE_RUN_STATUSES)}"
        )

    # Call database layer with filters
    db = get_database()
    conversations: List[DBDashboardConversation] = db.list_conversations(
        limit=limit,
        offset=offset,
        user_id=user.id,
        conversation_status=conversation_status,
        run_status=run_status,
    )

    # Convert and return (existing logic)
    return ConversationListResponse(
        conversations=[
            ConversationListItem(
                id=conv.id,
                url=conv.url,
                title=conv.title,
                import_date=conv.import_date,
                created_at=conv.created_at.isoformat(),
                updated_at=conv.updated_at.isoformat(),
                user_id=conv.user_id,
                user_name=conv.user_name,
                user_email=conv.user_email,
                idea_title=conv.idea_title,
                idea_abstract=conv.idea_abstract,
                last_user_message_content=conv.last_user_message_content,
                last_assistant_message_content=conv.last_assistant_message_content,
                manual_title=conv.manual_title,
                manual_hypothesis=conv.manual_hypothesis,
                status=conv.status,
            )
            for conv in conversations
        ]
    )
```

### Pattern 2: Dynamic Database Filtering

**Location:** `server/app/services/database/conversations.py` - Update `list_conversations` method

```python
def list_conversations(
    self,
    limit: int = 100,
    offset: int = 0,
    user_id: int | None = None,
    conversation_status: str | None = None,
    run_status: str | None = None,
) -> List[DashboardConversation]:
    """
    List conversations for dashboard with optional filtering.

    Args:
        limit: Max results (default 100, max 1000)
        offset: Pagination offset (default 0)
        user_id: Filter by user (required for API endpoint)
        conversation_status: Filter by "draft" or "with_research" (optional)
        run_status: Filter by run status (optional)

    Returns:
        List of DashboardConversation objects

    Note: Filters are ANDed together. When run_status is provided,
    only conversations with at least one matching run are returned.
    """
    with self._get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            # Start with base query
            query = """
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
                    c.manual_hypothesis,
                    c.status
                FROM conversations c
                LEFT JOIN users u ON c.imported_by_user_id = u.id
                LEFT JOIN ideas i ON i.conversation_id = c.id
                LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id
            """

            params: list = []
            where_conditions: list = []

            # Add user filter (required for API)
            if user_id is not None:
                where_conditions.append("c.imported_by_user_id = %s")
                params.append(user_id)

            # Add conversation status filter
            if conversation_status is not None:
                where_conditions.append("c.status = %s")
                params.append(conversation_status)

            # Add research run status filter with conditional JOIN
            if run_status is not None:
                # Add JOIN for research_pipeline_runs table
                query = query.replace(
                    "LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id",
                    "LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id\n" +
                    "LEFT JOIN research_pipeline_runs rpr ON rpr.idea_id = i.id"
                )
                # Add DISTINCT to handle multiple runs per conversation
                query = query.replace("SELECT", "SELECT DISTINCT")
                # Filter by run status
                where_conditions.append("rpr.status = %s")
                params.append(run_status)

            # Build complete WHERE clause
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)

            # Add ordering and pagination
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
            status=row["status"],
        )
        for row in rows
    ]
```

### Pattern 3: Error Response Consistency

**Location:** Already has `ErrorResponse` model, maintain consistency

```python
# Reuse existing ErrorResponse for all validation failures
class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")

# Example usage in endpoint:
if conversation_status not in CONVERSATION_STATUSES:
    response.status_code = 400
    return ErrorResponse(
        error="Invalid conversation_status",
        detail=f"Must be one of: {', '.join(CONVERSATION_STATUSES)}"
    )
```

---

## Async Considerations

### Current Pattern: Raw SQL with psycopg2
The codebase uses **synchronous** psycopg2 for database access, NOT async. This is fine for this feature because:

1. **Single Database Connection**: psycopg2 connections are typically thread-pooled, not async
2. **Existing Pattern**: All `list_conversations` methods are synchronous
3. **No Blocking**: Query execution is fast (simple WHERE clauses are not I/O intensive)

**No changes needed.** Keep using `with self._get_connection()` as-is.

### Endpoint-Level Async
The endpoint itself is `async def`, which is correct. FastAPI will run the synchronous database code in a thread pool automatically.

```python
# GOOD: Async endpoint with sync database calls
@router.get("")
async def list_conversations(...):  # Async endpoint
    db = get_database()
    conversations = db.list_conversations(...)  # Sync call, FastAPI handles threading
    return ConversationListResponse(...)
```

---

## Error Handling

### Validation Errors (HTTP 400)
Use `response.status_code` pattern already in codebase:

```python
# Invalid query parameter
if conversation_status not in CONVERSATION_STATUSES:
    response.status_code = 400
    return ErrorResponse(
        error="Invalid conversation_status",
        detail=f"Must be one of: {', '.join(CONVERSATION_STATUSES)}"
    )
```

### Authorization Errors (HTTP 401)
Already handled by `get_current_user(request)` - no changes needed.

### Not Found Errors (HTTP 404)
Not applicable for list endpoint (returns empty list if no matches).

### Server Errors (HTTP 500)
Existing error handling for database connection issues applies.

---

## OpenAPI Documentation

FastAPI automatically generates OpenAPI docs from type hints. The new parameters will appear in `/docs` with:

1. **Parameter name**: `conversation_status`, `run_status`
2. **Parameter type**: `string` (from `str | None`)
3. **Required**: false (from `= None` default)
4. **Description**: From docstring (see endpoint docstring in Pattern 1)
5. **Allowed values**: Not automatically documented (add manually with `Field()` if needed)

For clearer documentation of allowed values, consider using `Query()`:

```python
from fastapi import Query

@router.get("")
async def list_conversations(
    conversation_status: str | None = Query(
        None,
        description="Filter by conversation status: 'draft' or 'with_research'"
    ),
    run_status: str | None = Query(
        None,
        description="Filter by run status: 'pending', 'running', 'completed', or 'failed'"
    ),
):
```

This is optional but improves API documentation.

---

## Type Hints and Type Checking

### Current Setup (from pyproject.toml)
```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true       # All functions must have types!
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
```

### For This Feature: Strict Type Hints Required

```python
# GOOD: Complete type hints
@router.get("")
async def list_conversations(
    request: Request,
    response: Response,
    limit: int = 100,
    offset: int = 0,
    conversation_status: str | None = None,      # MUST have type hint
    run_status: str | None = None,                # MUST have type hint
) -> Union[ConversationListResponse, ErrorResponse]:  # MUST have return type
    """..."""
    pass

# Database method
def list_conversations(
    self,
    limit: int = 100,
    offset: int = 0,
    user_id: int | None = None,
    conversation_status: str | None = None,  # Types required
    run_status: str | None = None,            # Types required
) -> List[DashboardConversation]:             # Return type required
    """..."""
    pass
```

---

## For Executor

### Key Points to Follow

1. **Add two new optional query parameters** to `GET /conversations` endpoint:
   - `conversation_status: str | None = None`
   - `run_status: str | None = None`

2. **Validate BEFORE database call**:
   - Check `conversation_status in CONVERSATION_STATUSES` (if not None)
   - Check `run_status in PIPELINE_RUN_STATUSES` (if not None)
   - Return `ErrorResponse` with 400 status if invalid

3. **Update database method signature**:
   - Add same two parameters to `list_conversations()`
   - Keep defaults as `None` for both

4. **Build dynamic SQL WHERE clauses**:
   - Add `c.status = %s` when `conversation_status` is not None
   - Add `LEFT JOIN research_pipeline_runs rpr ON rpr.idea_id = i.id` when `run_status` is not None
   - Add `SELECT DISTINCT` when JOINing runs table
   - Add `rpr.status = %s` when `run_status` is not None
   - Combine WHERE conditions with AND
   - Always parameterize query parameters (use `%s` and `params` list)

5. **Maintain type safety**:
   - All type hints required (mypy strict mode is enabled)
   - Use `Union[ConversationListResponse, ErrorResponse]` as return type
   - Use `str | None` for optional parameters (Python 3.12 syntax)

6. **Follow existing patterns**:
   - Use `response.status_code = 400` for validation errors
   - Return `ErrorResponse(error="...", detail="...")` for errors
   - Keep endpoint handler simple, put SQL logic in database layer
   - Use `with self._get_connection()` pattern for database access

### Critical Warnings

1. **NEVER skip validation** - Always validate query params at endpoint level
2. **ALWAYS use parameterized queries** - Prevents SQL injection
3. **ALWAYS add DISTINCT** - When JOINing with runs table (one conversation can have multiple runs)
4. **ALWAYS provide type hints** - Project uses strict mypy configuration
5. **Test edge cases**:
   - Both filters active simultaneously
   - No conversations matching filters (returns empty list)
   - Invalid filter values (returns 400 error)

---

## Documentation References

- **FastAPI Query Parameters**: https://fastapi.tiangolo.com/tutorial/query-params/
- **FastAPI Error Handling**: https://fastapi.tiangolo.com/tutorial/handling-errors/
- **FastAPI Dependencies**: https://fastapi.tiangolo.com/tutorial/dependencies/
- **FastAPI Bigger Applications**: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- **Pydantic v2 Migration**: https://docs.pydantic.dev/latest/
- **Python 3.12 Type Hints**: https://docs.python.org/3/library/typing.html

---

## Compliance Summary

| Principle | Status | Notes |
|-----------|--------|-------|
| FastAPI 0.116 best practices | ✓ Following | Simple optional params, no Query() wrapper needed |
| Pydantic v2 patterns | ✓ Required | Use `str \| None`, not `Optional[str]` |
| Type safety | ✓ Strict | All functions must have complete type hints |
| Security | ✓ Parameterized | All SQL uses %s placeholders and params list |
| Async patterns | ✓ Correct | Async endpoint, sync DB calls (FastAPI handles threading) |
| Error handling | ✓ Consistent | Use existing ErrorResponse model and 400 status |
| Existing patterns | ✓ Match | Follow current endpoint/database layer separation |

---

## Next Steps

Ready for implementation. The architecture document (`02-architecture.md`) provides frontend and context details. This guidance covers the FastAPI/backend specifics needed to execute the feature correctly.

If you have questions about specific patterns or need clarification on any FastAPI concepts during implementation, refer to the **Documentation References** section or ask.
