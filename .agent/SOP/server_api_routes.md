# SOP: Server API Routes

## Related Documentation
- [Server Architecture](../System/server_architecture.md)
- [Project Architecture](../System/project_architecture.md)

---

## Overview

This SOP covers creating new API routes in the FastAPI server. Use this procedure when you need to:
- Add new REST endpoints
- Create new feature modules
- Expose server functionality via HTTP

---

## Prerequisites

- Python environment activated
- Understanding of the feature you're implementing
- Pydantic models defined for request/response

---

## Step-by-Step Procedure

### 1. Create the Route Module

Create a new file in `server/app/api/`:

```python
# server/app/api/my_feature.py
from fastapi import APIRouter, Request, Response
from app.middleware.auth import get_current_user
from app.services import get_database
from app.models import MyFeatureRequest, MyFeatureResponse

router = APIRouter(prefix="/my-feature", tags=["my-feature"])

# Initialize services at module level (singleton pattern)
db = get_database()
```

### 2. Define Request/Response Models

Create or update models in `server/app/models/`:

```python
# server/app/models/my_feature.py
from pydantic import BaseModel, Field
from typing import Optional, List

class MyFeatureRequest(BaseModel):
    """Request model for creating a feature."""
    name: str = Field(..., min_length=1, description="Feature name")
    description: Optional[str] = Field(None, description="Optional description")

class MyFeatureResponse(BaseModel):
    """Response model for feature data."""
    id: int
    name: str
    description: Optional[str]
    created_at: str
```

### 3. Export Models

Add exports to `server/app/models/__init__.py`:

```python
from app.models.my_feature import MyFeatureRequest, MyFeatureResponse

__all__ = [
    # ... existing exports
    "MyFeatureRequest",
    "MyFeatureResponse",
]
```

### 4. Implement Route Handlers

Add endpoints to your route module:

```python
# server/app/api/my_feature.py

@router.get("/")
async def list_features(request: Request) -> List[MyFeatureResponse]:
    """List all features for the current user."""
    user = get_current_user(request)
    features = db.list_features(user.id)
    return [MyFeatureResponse(**f) for f in features]


@router.get("/{feature_id}")
async def get_feature(feature_id: int, request: Request) -> MyFeatureResponse:
    """Get a specific feature by ID."""
    user = get_current_user(request)
    feature = db.get_feature(feature_id, user.id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return MyFeatureResponse(**feature)


@router.post("/", status_code=201)
async def create_feature(
    data: MyFeatureRequest,
    request: Request
) -> MyFeatureResponse:
    """Create a new feature."""
    user = get_current_user(request)
    feature = db.create_feature(data.model_dump(), user.id)
    return MyFeatureResponse(**feature)


@router.patch("/{feature_id}")
async def update_feature(
    feature_id: int,
    data: MyFeatureRequest,
    request: Request
) -> MyFeatureResponse:
    """Update an existing feature."""
    user = get_current_user(request)
    feature = db.update_feature(feature_id, data.model_dump(), user.id)
    return MyFeatureResponse(**feature)


@router.delete("/{feature_id}", status_code=204)
async def delete_feature(feature_id: int, request: Request) -> None:
    """Delete a feature."""
    user = get_current_user(request)
    db.delete_feature(feature_id, user.id)
```

### 5. Register the Router

Add the router to `server/app/routes.py`:

```python
from app.api.my_feature import router as my_feature_router

router = APIRouter(prefix="/api")
# ... existing routers
router.include_router(my_feature_router)
```

### 6. Add Database Methods (if needed)

Create a new mixin in `server/app/services/database/`:

```python
# server/app/services/database/my_feature.py
from typing import List, Optional, Dict, Any

class MyFeatureMixin:
    """Database operations for my_feature table."""

    def list_features(self, user_id: int) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM my_features WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,)
                )
                return cur.fetchall()

    def create_feature(self, data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO my_features (name, description, user_id, created_at, updated_at)
                    VALUES (%s, %s, %s, NOW(), NOW())
                    RETURNING *
                    """,
                    (data["name"], data.get("description"), user_id)
                )
                conn.commit()
                return cur.fetchone()
```

### 7. Include Mixin in DatabaseManager

Update `server/app/services/database/__init__.py`:

```python
from .my_feature import MyFeatureMixin

class DatabaseManager(
    BaseDatabaseManager,
    MyFeatureMixin,  # Add new mixin
    # ... other mixins
):
    pass
```

---

## Key Files

| File | Purpose |
|------|---------|
| `server/app/api/` | Route modules directory |
| `server/app/routes.py` | Central router registration |
| `server/app/models/` | Pydantic request/response models |
| `server/app/middleware/auth.py` | Authentication utilities |
| `server/app/services/database/` | Database mixins |

---

## Authentication Patterns

### User Authentication (Session Cookie)

```python
from app.middleware.auth import get_current_user

@router.get("/protected")
async def protected_route(request: Request):
    user = get_current_user(request)
    # user.id, user.email, user.name available
```

### Optional Authentication

```python
from app.middleware.auth import get_current_user_optional

@router.get("/public")
async def public_route(request: Request):
    user = get_current_user_optional(request)
    if user:
        # Authenticated user
    else:
        # Anonymous access
```

---

## Union Response Pattern for "Not Found" States

> Added from: auto-evaluation-details-ui implementation (2025-12-09)

When "not found" is a valid business state rather than an error (e.g., review doesn't exist yet for a run, settings not configured), return a typed response instead of HTTP 404.

### When to Use

- Resource existence is expected to vary (not an error condition)
- Frontend needs to distinguish between "not found" and actual errors
- You want to return additional context about why the resource doesn't exist

### When NOT to Use

- Resource should always exist (use HTTP 404)
- Unauthorized access (use HTTP 403)
- Invalid parameters (use HTTP 400)

### Implementation Pattern

**Define response models:**
```python
# server/app/models/my_feature.py
from pydantic import BaseModel, Field
from typing import Union

class MyResourceResponse(BaseModel):
    """Response when resource exists."""
    id: int
    name: str
    data: str

class MyResourceNotFoundResponse(BaseModel):
    """Response when resource doesn't exist (expected state)."""
    resource_id: str = Field(..., description="Identifier that was searched")
    exists: bool = Field(False, description="Always False for not-found response")
    message: str = Field(..., description="User-friendly explanation")
```

**Endpoint with Union response:**
```python
# server/app/api/my_feature.py
from typing import Union

@router.get(
    "/{resource_id}",
    response_model=Union[MyResourceResponse, MyResourceNotFoundResponse]
)
def get_resource(resource_id: str, request: Request):
    """Fetch resource by ID. Returns NotFoundResponse if resource doesn't exist."""
    # Auth and ownership validation...

    resource = db.get_resource(resource_id)
    if resource is None:
        return MyResourceNotFoundResponse(
            resource_id=resource_id,
            exists=False,
            message="No data available for this resource yet"
        )

    return MyResourceResponse(
        id=resource["id"],
        name=resource["name"],
        data=resource["data"]
    )
```

**Frontend type guard:**
```typescript
// types/myFeature.ts
export interface MyResourceResponse {
  id: number;
  name: string;
  data: string;
}

export interface MyResourceNotFoundResponse {
  resource_id: string;
  exists: false;
  message: string;
}

// Type guard to discriminate union
export function isResource(
  response: MyResourceResponse | MyResourceNotFoundResponse
): response is MyResourceResponse {
  return "id" in response && "name" in response;
}

// Usage in component
const response = await apiFetch<MyResourceResponse | MyResourceNotFoundResponse>(url);
if (isResource(response)) {
  setData(response);
} else {
  setNotFound(true);
  setMessage(response.message);
}
```

### Reference Implementation

See `server/app/api/research_pipeline_runs.py` endpoint `get_research_run_review()` and `frontend/src/features/research/hooks/useReviewData.ts`.

---

## Common Pitfalls

- **Always import router in routes.py**: Router won't be registered otherwise
- **Use correct HTTP methods**: GET for read, POST for create, PATCH for update, DELETE for remove
- **Return proper status codes**: 201 for created, 204 for no content, 404 for not found
- **Validate request data**: Use Pydantic models with Field validators
- **Handle authentication**: Use `get_current_user()` for protected routes
- **Don't expose sensitive data**: Filter response data appropriately

---

## Verification

1. Start the server:
   ```bash
   cd server
   make dev
   ```

2. Check the endpoint appears in OpenAPI docs:
   - Open http://localhost:8000/docs
   - Verify your routes appear under the correct tag

3. Test with curl:
   ```bash
   curl http://localhost:8000/api/my-feature
   ```

4. Run tests if available:
   ```bash
   make test
   ```
