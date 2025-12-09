# SOP: Server Services

## Related Documentation
- [Server Architecture](../System/server_architecture.md)
- [Project Architecture](../System/project_architecture.md)

---

## Overview

This SOP covers creating new services in the FastAPI server. Use this procedure when you need to:
- Add business logic that spans multiple routes
- Integrate with external APIs
- Create reusable functionality
- Add database access for new tables

---

## Prerequisites

- Python environment activated
- Understanding of the service's responsibility
- Knowledge of dependencies (database, external APIs, etc.)

---

## Step-by-Step Procedure

### 1. Create the Service File

Create a new file in `server/app/services/`:

```python
# server/app/services/my_service.py
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class MyService:
    """Service for handling my feature logic."""

    def __init__(self, dependency: Optional[OtherService] = None):
        """Initialize the service with dependencies."""
        self.dependency = dependency
        logger.info("MyService initialized")

    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data and return result."""
        try:
            # Business logic here
            result = self._transform(data)
            logger.info(f"Processed data: {result.get('id')}")
            return result
        except Exception as e:
            logger.error(f"Error processing data: {e}")
            raise

    def _transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Internal transformation logic."""
        return {
            "id": data.get("id"),
            "processed": True,
            "value": data.get("value", 0) * 2
        }
```

### 2. Export the Service

Add to `server/app/services/__init__.py`:

```python
from .my_service import MyService

__all__ = [
    # ... existing exports
    "MyService",
]
```

### 3. Use the Service in Routes

Initialize at module level for singleton pattern:

```python
# server/app/api/my_feature.py
from app.services import MyService, OtherService

# Initialize services at module level
other_service = OtherService()
my_service = MyService(dependency=other_service)

@router.post("/process")
async def process(data: ProcessRequest, request: Request):
    result = my_service.process_data(data.model_dump())
    return result
```

---

## Database Service Pattern (Mixin)

For services that need database access, create a mixin:

### 1. Create the Mixin

```python
# server/app/services/database/my_table.py
from typing import List, Optional, Dict, Any
import psycopg2.extras


class MyTableMixin:
    """Database operations for my_table."""

    def get_my_item(self, item_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get a single item by ID."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM my_table
                    WHERE id = %s AND user_id = %s
                    """,
                    (item_id, user_id)
                )
                return cur.fetchone()

    def list_my_items(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List items with pagination."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM my_table
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, limit, offset)
                )
                return cur.fetchall()

    def create_my_item(self, data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Create a new item."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO my_table (name, value, user_id, created_at, updated_at)
                    VALUES (%s, %s, %s, NOW(), NOW())
                    RETURNING *
                    """,
                    (data["name"], data.get("value"), user_id)
                )
                conn.commit()
                return cur.fetchone()

    def update_my_item(
        self,
        item_id: int,
        data: Dict[str, Any],
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Update an existing item."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    UPDATE my_table
                    SET name = %s, value = %s, updated_at = NOW()
                    WHERE id = %s AND user_id = %s
                    RETURNING *
                    """,
                    (data["name"], data.get("value"), item_id, user_id)
                )
                conn.commit()
                return cur.fetchone()

    def delete_my_item(self, item_id: int, user_id: int) -> bool:
        """Delete an item."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM my_table
                    WHERE id = %s AND user_id = %s
                    """,
                    (item_id, user_id)
                )
                conn.commit()
                return cur.rowcount > 0
```

### 2. Add Mixin to DatabaseManager

```python
# server/app/services/database/__init__.py
from .base import BaseDatabaseManager
from .my_table import MyTableMixin
# ... other imports

class DatabaseManager(
    BaseDatabaseManager,
    MyTableMixin,  # Add your mixin
    ConversationsMixin,
    IdeasMixin,
    # ... other mixins
):
    """Combined database manager with all mixins."""
    pass


# Singleton pattern
_db_instance: Optional[DatabaseManager] = None


def get_database() -> DatabaseManager:
    """Get the singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
```

---

## External API Service Pattern

For services integrating with external APIs:

```python
# server/app/services/external_api_service.py
import httpx
from typing import Optional, Dict, Any
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class ExternalApiService:
    """Service for integrating with External API."""

    BASE_URL = "https://api.external.com/v1"

    def __init__(self):
        self.api_key = settings.EXTERNAL_API_KEY
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
        return self._client

    async def fetch_data(self, resource_id: str) -> Dict[str, Any]:
        """Fetch data from external API."""
        client = await self._get_client()
        try:
            response = await client.get(f"/resources/{resource_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"External API error: {e}")
            raise

    async def create_resource(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create resource in external API."""
        client = await self._get_client()
        response = await client.post("/resources", json=data)
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
```

---

## LLM Service Pattern

For services that interact with LLMs:

```python
# server/app/services/my_llm_service.py
from typing import AsyncGenerator
from app.services.langchain_llm_service import LangChainLLMService


class MyLLMService(LangChainLLMService):
    """Service extending LangChain LLM capabilities."""

    async def generate_custom_output(
        self,
        llm_model: str,
        input_text: str,
    ) -> AsyncGenerator[str, None]:
        """Generate custom output with streaming."""
        system_prompt = "You are a helpful assistant."

        async for chunk in self._stream_completion(
            llm_model=llm_model,
            system_prompt=system_prompt,
            user_message=input_text,
        ):
            yield chunk
```

---

## Key Files

| File | Purpose |
|------|---------|
| `server/app/services/` | Service classes directory |
| `server/app/services/__init__.py` | Service exports and `get_database()` |
| `server/app/services/database/` | Database mixin classes |
| `server/app/services/database/base.py` | Base database manager |
| `server/app/config.py` | Configuration settings |

---

## Service Organization

| Service Type | Location | Pattern |
|--------------|----------|---------|
| Business Logic | `app/services/my_service.py` | Class with methods |
| Database Access | `app/services/database/my_table.py` | Mixin class |
| LLM Integration | `app/services/langchain_llm_service.py` | Async class |
| External API | `app/services/mem0_service.py` | HTTP client class |
| File Processing | `app/services/pdf_service.py` | Utility class |

---

## Common Pitfalls

- **Don't use ORM**: Project uses raw SQL with psycopg2
- **Always use parameterized queries**: Prevent SQL injection with `%s` placeholders
- **Commit transactions**: Use `conn.commit()` after INSERT/UPDATE/DELETE
- **Handle connections properly**: Use context managers (`with`)
- **Log errors**: Use Python logging for debugging
- **Initialize at module level**: Services should be singletons
- **Don't store state**: Services should be stateless between requests

---

## Transaction-Safe Helper Pattern

> Added from: conversation-status-tracking implementation (2025-12-08)

When an operation needs to participate in an existing transaction (e.g., update conversation status when creating a research run), create a helper method that accepts a cursor parameter.

### When to Use

- Multi-step operations that must be atomic (all-or-nothing)
- One operation triggers a side effect in another table
- Status updates tied to record creation

### Implementation

Create a pair of methods: public method + cursor helper:

```python
# server/app/services/database/my_table.py

# Validation constant at module level
ALLOWED_STATUSES = ('draft', 'active', 'completed')


class MyTableMixin:
    """Database operations for my_table."""

    def update_status(self, item_id: int, status: str) -> bool:
        """
        Public method - manages its own transaction.

        Returns True if updated, False if not found.
        """
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Invalid status '{status}'")

        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE my_table SET status = %s, updated_at = %s WHERE id = %s",
                    (status, now, item_id),
                )
                conn.commit()
                return bool(cursor.rowcount > 0)

    def _update_status_with_cursor(
        self, cursor, item_id: int, status: str
    ) -> None:
        """
        Transaction helper - uses existing cursor, NO commit.

        Called by other mixins that need atomic multi-step operations.
        The caller is responsible for committing.
        """
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Invalid status '{status}'")

        now = datetime.now()
        cursor.execute(
            "UPDATE my_table SET status = %s, updated_at = %s WHERE id = %s",
            (status, now, item_id),
        )
        # NOTE: No conn.commit() - caller handles transaction
```

### Usage in Multi-Step Operations

```python
# server/app/services/database/related_table.py

class RelatedTableMixin:
    def create_related_item(self, *, item_id: int, data: dict) -> int:
        """Create related item and update parent status atomically."""
        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # Step 1: Insert new record
                cursor.execute(
                    "INSERT INTO related_table (...) VALUES (...) RETURNING id",
                    (...)
                )
                new_id = cursor.fetchone()[0]

                # Step 2: Update parent status (atomic with insert)
                self._update_status_with_cursor(
                    cursor=cursor,
                    item_id=item_id,
                    status='active',
                )

                # Step 3: Commit entire transaction
                conn.commit()
                return new_id
```

### Key Points

1. **Helper method naming**: Prefix with underscore and suffix with `_with_cursor`
2. **No commit in helpers**: The calling method handles the transaction boundary
3. **Validation in both methods**: Always validate input even in helper methods
4. **Cross-mixin calls**: Works because all mixins are composed into DatabaseManager via `self`

---

## Verification

1. Import the service in Python REPL:
   ```python
   from app.services import MyService
   service = MyService()
   ```

2. Test the database mixin:
   ```python
   from app.services import get_database
   db = get_database()
   items = db.list_my_items(user_id=1)
   ```

3. Run existing tests:
   ```bash
   make test
   ```

4. Test via API endpoint:
   ```bash
   curl -X POST http://localhost:8000/api/my-feature/process \
     -H "Content-Type: application/json" \
     -d '{"name": "test"}'
   ```
