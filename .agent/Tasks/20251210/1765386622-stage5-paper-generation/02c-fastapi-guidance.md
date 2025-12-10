# FastAPI Technical Guidance: Paper Generation Progress Endpoints

**Agent**: fastapi-expert

**Timestamp**: 2025-12-10 20:45 UTC

**Status**: Pending Approval

---

## Project Analysis

### Detected Stack
| Package | Version | Notes |
|---------|---------|-------|
| FastAPI | 0.116.1 | Modern async framework with Annotated support |
| Pydantic | 2.x (implicit) | Used in codebase (v2 syntax in models) |
| Uvicorn | 0.35.0 | Production ASGI server |
| Python | 3.12 | Type hints with `|` union syntax |
| PostgreSQL | Current | Via psycopg2 driver |

### Pydantic Version
**Pydantic v2** - The project imports `from pydantic import BaseModel` without legacy config patterns. This affects all model syntax.

### Key Architecture Facts
- **Bearer token auth**: TELEMETRY_WEBHOOK_TOKEN in settings
- **Event pattern**: BaseEvent dataclass hierarchy with `persistence_record()` method
- **Database**: Direct psycopg2 queries with RealDictCursor
- **SSE streaming**: Uses AsyncGenerator pattern in research_pipeline_runs.py
- **Webhook receiving**: Existing endpoints in research_pipeline_events.py follow pattern

---

## Version-Specific Guidance

### FastAPI 0.116 Patterns (Your Version)
- ✅ Use `Annotated[type, ...]` for path/query parameters (preferred over direct parameters)
- ✅ Use `async def` for all endpoints (non-blocking)
- ✅ Use `HTTPException` with `status_code` enum values
- ✅ Use `BaseModel` for request/response serialization
- ✅ Pydantic v2 models: `Field()`, `field_validator`, `ConfigDict`
- ✅ Type hints with `|` (Python 3.12) instead of `Optional[X]`

### Pydantic v2 Patterns (Your Version)
```python
# v2 Syntax (CORRECT for this project)
from pydantic import BaseModel, Field

class MyModel(BaseModel):
    name: str = Field(..., description="Field description")
    age: int | None = Field(default=None, ge=0)

# Converting models
data_dict = model.model_dump()  # Not .dict()
json_str = model.model_dump_json()  # Not .json()
```

### Do's for This Project ✅
1. **Follow existing webhook pattern** - Match `StageProgressPayload` structure exactly
2. **Use Bearer token verification** - Reuse `_verify_bearer_token()` dependency
3. **Return 204 No Content** - Webhooks don't need response bodies
4. **Create NamedTuple for DB rows** - Match `StageProgressEvent` pattern
5. **Use psycopg2.extras.RealDictCursor** - Consistency with existing code
6. **Emit from SSE generator** - Add to existing polling loop in stream_research_run_events()
7. **Type all function signatures** - Project enforces mypy strict mode
8. **Use dataclass for backend events** - Match `RunStageProgressEvent` pattern

### Don'ts for This Project ❌
1. Don't use `@router.on_event()` - Use lifespan parameter (but not needed here)
2. Don't use blocking calls in async functions - Use `await` or move to background
3. Don't skip type hints - Strict mypy enforced
4. Don't create database connections in endpoints - Use dependency injection
5. Don't return response bodies from webhooks - 204 No Content is standard
6. Don't use Optional[X] - Use `X | None` (Python 3.12)
7. Don't skip Bearer token validation - Always verify TELEMETRY_WEBHOOK_TOKEN

---

## Paper Generation Progress: Pydantic Models

### Request Model (Webhook Input)

```python
from pydantic import BaseModel, Field
from typing import Any, Optional

class PaperGenerationProgressEvent(BaseModel):
    """Single paper generation event from the pipeline."""
    step: str = Field(..., description="Step name: 'plot_aggregation', 'citation_gathering', 'paper_writeup', 'paper_review'")
    substep: str | None = Field(default=None, description="Substep identifier (e.g., 'round_1', 'revision_2')")
    progress: float = Field(..., description="Overall progress 0.0-1.0", ge=0.0, le=1.0)
    step_progress: float = Field(..., description="Step-specific progress 0.0-1.0", ge=0.0, le=1.0)
    details: dict[str, Any] | None = Field(
        default=None,
        description="Step-specific metadata: {plot_aggregation: {figures_count, reflection_loops}, citation_gathering: {citations_found, source_count}, paper_writeup: {words_written, sections_completed}, paper_review: {score, feedback}}"
    )


class PaperGenerationProgressPayload(BaseModel):
    """Webhook payload matching existing StageProgressPayload pattern."""
    run_id: str = Field(..., description="Research run identifier")
    event: PaperGenerationProgressEvent = Field(..., description="Event details")
```

**Why this structure**:
- `step` identifies the 4 major phases (not multiple progress events)
- `substep` tracks finer iterations within a step (e.g., review round 1, 2, 3)
- `progress` is overall 0-1 for the entire paper generation stage
- `step_progress` is 0-1 for just this step, enabling sub-progress visualization
- `details` is flexible JSONB for step-specific metadata (figure count, review scores, etc.)

### Response Model (GET Endpoint)

```python
from pydantic import BaseModel, Field
from datetime import datetime

class PaperGenerationEventResponse(BaseModel):
    """Single event returned from GET endpoint."""
    id: int = Field(..., description="Unique event ID")
    run_id: str = Field(..., description="Research run ID")
    step: str = Field(..., description="Step: plot_aggregation|citation_gathering|paper_writeup|paper_review")
    substep: str | None = Field(default=None)
    progress: float = Field(..., description="Overall progress 0-1")
    step_progress: float = Field(..., description="Step progress 0-1")
    details: dict[str, Any] | None = Field(default=None)
    created_at: datetime = Field(..., description="Event timestamp")


class PaperGenerationProgressResponse(BaseModel):
    """Response for GET /runs/{run_id}/paper-generation-progress."""
    run_id: str = Field(..., description="Research run ID")
    events: list[PaperGenerationEventResponse] = Field(
        default_factory=list,
        description="Chronologically ordered events"
    )
    latest_step: str | None = Field(
        default=None,
        description="Current step, e.g., 'paper_review'"
    )
    overall_progress: float = Field(
        default=0.0,
        description="Overall progress 0-1 from latest event"
    )
```

**Why this response**:
- Matches existing response pattern (list of events + summary fields)
- `latest_step` helps frontend know which section to highlight
- `overall_progress` avoids re-calculating from events
- `created_at` as datetime (Pydantic serializes to ISO 8601 string automatically)

---

## Database Query Pattern (rp_events.py)

### NamedTuple Definition

```python
from datetime import datetime
from typing import Any, NamedTuple, Optional

class PaperGenerationEvent(NamedTuple):
    """Maps database row to Python object."""
    id: int
    run_id: str
    step: str  # plot_aggregation|citation_gathering|paper_writeup|paper_review
    substep: str | None
    progress: float  # 0.0-1.0
    step_progress: float  # 0.0-1.0
    details: dict[str, Any] | None  # JSONB deserialized to dict
    created_at: datetime
```

### Query Method in ResearchPipelineEventsMixin

```python
def list_paper_generation_events(self, run_id: str) -> list[PaperGenerationEvent]:
    """Fetch all paper generation events for a run, ordered chronologically."""
    query = """
        SELECT id, run_id, step, substep, progress, step_progress, details, created_at
        FROM rp_paper_generation_events
        WHERE run_id = %s
        ORDER BY created_at ASC
    """
    with self._get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(query, (run_id,))
            rows = cursor.fetchall() or []
    return [PaperGenerationEvent(**row) for row in rows]


def get_latest_paper_generation_event(self, run_id: str) -> Optional[PaperGenerationEvent]:
    """Fetch most recent paper generation event for a run."""
    query = """
        SELECT id, run_id, step, substep, progress, step_progress, details, created_at
        FROM rp_paper_generation_events
        WHERE run_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """
    with self._get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(query, (run_id,))
            row = cursor.fetchone()
    return PaperGenerationEvent(**row) if row else None
```

**Why this approach**:
- Matches exact pattern used by StageProgressEvent
- RealDictCursor automatically deserializes JSONB `details` to dict
- Chronological ordering (ASC) for event stream
- Separate method for latest event for SSE optimization

---

## Webhook Endpoint Pattern (research_pipeline_events.py)

### POST Endpoint Implementation

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import None as NoneType

@router.post(
    "/paper-generation-progress",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Receive paper generation progress from pipeline",
    tags=["research-pipeline-events"]
)
def ingest_paper_generation_progress(
    payload: PaperGenerationProgressPayload,
    _: NoneType = Depends(_verify_bearer_token),
) -> None:
    """
    Webhook endpoint for receiving paper generation progress events.

    Called by the research pipeline during:
    - Plot aggregation phase
    - Citation gathering phase
    - Paper writeup phase
    - Paper review phase

    Requires bearer token in Authorization header.
    Returns 204 No Content on success.
    """
    event = payload.event
    logger.info(
        "Paper generation progress: run=%s step=%s substep=%s progress=%.1f%% step_progress=%.1f%%",
        payload.run_id,
        event.step,
        event.substep or "N/A",
        event.progress * 100,
        event.step_progress * 100,
    )
    # Note: Persistence happens in event_persistence.py (backend pipeline)
    # This endpoint just logs; actual DB insert via event_callback in pipeline
```

**Why this pattern**:
- Returns `None` for 204 No Content response
- Uses `_verify_bearer_token` dependency (reused from other endpoints)
- Logs for debugging pipeline issues
- Minimal logic (webhook is fire-and-forget)
- Matches existing `ingest_stage_progress()` pattern exactly

---

## SSE Integration Pattern (research_pipeline_runs.py)

### 1. Add to Initial Data Fetch

```python
# In stream_research_run_events(), around line 733:

if not initial_sent:
    stage_events = [
        _stage_event_to_model(e).model_dump()
        for e in db.list_stage_progress_events(run_id=run_id)
    ]
    # ... other events ...

    # NEW: Add paper generation events
    paper_gen_events = [
        _paper_generation_event_to_model(e).model_dump()
        for e in db.list_paper_generation_events(run_id=run_id)
    ]

    initial_data = {
        "run": _run_to_info(current_run).model_dump(),
        "stage_progress": stage_events,
        "logs": log_events,
        "substage_events": substage_events,
        "artifacts": artifacts,
        "events": run_events,
        "paper_generation_progress": paper_gen_events,  # NEW
    }
    yield f"data: {json.dumps({'type': 'initial', 'data': initial_data})}\n\n"
```

### 2. Add Polling Logic

```python
# After stage progress polling, around line 780:

# Check and emit paper generation progress events
last_paper_gen_event: Optional[PaperGenerationEvent] = None
# (Initialize at top of event_generator function)

all_paper_gen = db.list_paper_generation_events(run_id=run_id)
if all_paper_gen:
    curr_paper_gen = all_paper_gen[-1]  # Most recent
    if curr_paper_gen != last_paper_gen_event:
        paper_gen_data = _paper_generation_event_to_model(curr_paper_gen)
        yield f"data: {json.dumps({'type': 'paper_generation_progress', 'data': paper_gen_data.model_dump()})}\n\n"
        last_paper_gen_event = curr_paper_gen
```

### 3. Add Converter Function

```python
from app.models import ResearchRunPaperGenerationProgress  # Create in models

def _paper_generation_event_to_model(
    event: PaperGenerationEvent,
) -> ResearchRunPaperGenerationProgress:
    """Convert database row to API response model."""
    return ResearchRunPaperGenerationProgress(
        id=event.id,
        run_id=event.run_id,
        step=event.step,
        substep=event.substep,
        progress=event.progress,
        step_progress=event.step_progress,
        details=event.details,
        created_at=event.created_at.isoformat(),
    )
```

**Why this pattern**:
- Matches existing `_stage_event_to_model()` pattern exactly
- Initial data includes all past events (important for page refresh)
- Polling detects new events and emits them
- `type: 'paper_generation_progress'` is distinct event type for frontend
- Converts NamedTuple to Pydantic model for serialization

---

## GET Endpoint Pattern

### Implementation in research_pipeline_runs.py (or new file if preferred)

```python
from fastapi import APIRouter, HTTPException, Request, status
from app.models import PaperGenerationProgressResponse
from app.middleware.auth import get_current_user

@router.get(
    "/{conversation_id}/idea/research-run/{run_id}/paper-generation-progress",
    response_model=PaperGenerationProgressResponse,
    summary="Get paper generation progress events",
    tags=["research-pipeline"]
)
def get_paper_generation_progress(
    conversation_id: int,
    run_id: str,
    request: Request,
) -> PaperGenerationProgressResponse:
    """
    Fetch all paper generation progress events for a research run.

    Returns chronologically ordered events plus summary fields.
    Requires authentication (user must own the conversation).
    """
    # Validation
    if conversation_id <= 0:
        raise HTTPException(status_code=400, detail="conversation_id must be positive")

    # Auth & ownership
    user = get_current_user(request)
    db = get_database()

    conversation = db.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this conversation")

    # Run ownership
    run = db.get_run_for_conversation(run_id=run_id, conversation_id=conversation_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Research run not found")

    # Fetch events
    events = db.list_paper_generation_events(run_id=run_id)
    event_models = [_paper_generation_event_to_model(e) for e in events]

    # Compute summary fields
    latest_event = events[-1] if events else None
    latest_step = latest_event.step if latest_event else None
    overall_progress = latest_event.progress if latest_event else 0.0

    return PaperGenerationProgressResponse(
        run_id=run_id,
        events=event_models,
        latest_step=latest_step,
        overall_progress=overall_progress,
    )
```

**Why this pattern**:
- Matches existing GET endpoint patterns (auth + ownership checks)
- Uses same ownership validation as `get_research_run_details()`
- Returns empty list gracefully if no events
- Computes summary fields from events (single source of truth)
- Type-hints everything for mypy strict mode

---

## Backend Event Emission (Pipeline Integration)

### PaperGenerationProgressEvent Class

Add to `research_pipeline/ai_scientist/treesearch/events.py`:

```python
@dataclass(frozen=True)
class PaperGenerationProgressEvent(BaseEvent):
    """Event emitted during paper generation phase (Stage 5)."""

    run_id: str  # Added for webhook payload
    step: str  # plot_aggregation|citation_gathering|paper_writeup|paper_review
    substep: str | None
    progress: float  # 0-1
    step_progress: float  # 0-1
    details: dict[str, Any] | None = None

    def type(self) -> str:
        return "ai.run.paper_generation_progress"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "step": self.step,
            "progress": self.progress,
            "step_progress": self.step_progress,
        }
        if self.substep:
            data["substep"] = self.substep
        if self.details:
            data["details"] = self.details
        return data

    def persistence_record(self) -> PersistenceRecord:
        return (
            "paper_generation_progress",
            {
                "step": self.step,
                "substep": self.substep,
                "progress": float(self.progress),
                "step_progress": float(self.step_progress),
                "details": self.details,
            },
        )
```

### Update EventKind Literal

In same file, update line 4:

```python
EventKind = Literal[
    "run_stage_progress",
    "run_log",
    "substage_completed",
    "paper_generation_progress",  # NEW
]
```

---

## Common Mistakes to Avoid

### Mistake 1: Forgetting Bearer Token Validation
```python
# WRONG - No validation
@router.post("/paper-generation-progress")
def ingest_paper_generation_progress(payload: PaperGenerationProgressPayload):
    ...

# RIGHT - Uses dependency
@router.post("/paper-generation-progress", status_code=204)
def ingest_paper_generation_progress(
    payload: PaperGenerationProgressPayload,
    _: None = Depends(_verify_bearer_token),
):
    ...
```

### Mistake 2: Returning Data from Webhook
```python
# WRONG - Returns data body
@router.post("/paper-generation-progress")
def ingest(...):
    return {"status": "ok"}  # 200 with body

# RIGHT - No response body
@router.post("/paper-generation-progress", status_code=204)
def ingest(...) -> None:
    ...  # 204 No Content
```

### Mistake 3: Blocking Calls in Async SSE
```python
# WRONG - time.sleep() blocks event loop
async def event_generator():
    while True:
        time.sleep(2)  # Blocks!
        yield data

# RIGHT - Use asyncio.sleep()
async def event_generator():
    while True:
        await asyncio.sleep(2)  # Non-blocking
        yield data
```

### Mistake 4: Missing Type Hints
```python
# WRONG - mypy will fail
def get_paper_gen_events(run_id):
    return db.list_paper_generation_events(run_id)

# RIGHT - Full type hints
def get_paper_gen_events(run_id: str) -> list[PaperGenerationEvent]:
    return db.list_paper_generation_events(run_id)
```

### Mistake 5: Using Optional[X] Instead of X | None
```python
# WRONG - Old Python syntax
from typing import Optional
step: Optional[str] = None

# RIGHT - Python 3.12 syntax (your project uses this)
step: str | None = None
```

---

## Key Recommendations for Executor

### Phase 1: Database
1. Create migration `XXXX_rp_paper_generation_events.py` with:
   - Table: `rp_paper_generation_events`
   - Columns: `id` (BigInt), `run_id` (Text), `step` (Text), `substep` (Text), `progress` (Float), `step_progress` (Float), `details` (JSONB), `created_at` (Timestamp)
   - Indexes: `idx_rp_paper_generation_events_run_id`, `idx_rp_paper_generation_events_created_at`
2. Follow pattern from `0004_rp_event_tables.py` and `0012_substage_completed_events.py`

### Phase 2: Backend Event Infrastructure
1. Add `PaperGenerationProgressEvent` class to `events.py`
2. Update `EventKind` Literal to include `"paper_generation_progress"`
3. Add `_insert_paper_generation_progress()` method to EventPersistenceManager
4. Update `_EVENT_PATHS` dict to include `'paper_generation_progress': '/paper-generation-progress'`
5. Update `_persist_event()` switch statement to handle new event type

### Phase 3: Server Webhook & GET Endpoints
1. Add Pydantic models to `models/` (PaperGenerationProgressEvent, PaperGenerationProgressPayload, PaperGenerationProgressResponse)
2. Add webhook endpoint to `research_pipeline_events.py` (POST /paper-generation-progress)
3. Add database methods to `rp_events.py` (list_paper_generation_events, get_latest_paper_generation_event, PaperGenerationEvent NamedTuple)
4. Add GET endpoint to `research_pipeline_runs.py` (GET /{conversation_id}/idea/research-run/{run_id}/paper-generation-progress)

### Phase 4: SSE Integration
1. Update `stream_research_run_events()` to include paper gen events in initial data
2. Add polling logic for new paper generation events
3. Add `_paper_generation_event_to_model()` converter function
4. Ensure converter creates Pydantic model for serialization

### Critical Points
- **Always use Bearer token verification** on webhook endpoint
- **Always use 204 No Content** for webhook response (no body)
- **Always use Pydantic v2 syntax** (model_dump(), Field(), ConfigDict)
- **Always type hint everything** (mypy strict mode enforced)
- **Always use `|` not `Optional`** (Python 3.12)
- **Always match existing patterns exactly** for consistency

---

## FastAPI/Pydantic Reference Links

- [FastAPI 0.116 Docs](https://fastapi.tiangolo.com/): Latest features
- [Pydantic v2 Migration](https://docs.pydantic.dev/latest/concepts/models/): Model syntax
- [HTTPException Status Codes](https://fastapi.tiangolo.com/tutorial/handling-errors/): Correct status codes
- [Bearer Token Verification](https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/): Auth patterns
- [SSE with FastAPI](https://fastapi.tiangolo.com/advanced/graphql/#subscription): Streaming patterns

---

## For Implementation Team

**Verification Checklist Before Starting**:
- [ ] FastAPI version 0.116.1 confirmed? (Project uses this)
- [ ] Pydantic v2 models confirmed? (No `class Config:`)
- [ ] Bearer token configured in `.env` as `TELEMETRY_WEBHOOK_TOKEN`?
- [ ] Database connection string available?
- [ ] Can run Alembic migrations?
- [ ] TypeScript models will be added by NextJS expert?

**Questions for Review**:
1. Should `details` field be required or optional? (Guidance: Optional for flexibility)
2. Should we store raw event or also log to research_pipeline_run_events? (Guidance: Just the dedicated table; webhook handler logs only)
3. Any additional fields needed in `details` for frontend visualization? (Guidance: Depends on frontend requirements from NextJS expert)

---

**STATUS**: Awaiting Approval

Please review the FastAPI guidance. Reply with:
- **"proceed"** or **"yes"** - Guidance is correct, continue to implementation
- **"modify: [your feedback]"** - I'll adjust the recommendations
- **"elaborate: [topic]"** - I'll provide more details on specific patterns
- **"stop"** - Pause here for discussion

---
