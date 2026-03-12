# Narrator Architecture

The Narrator transforms research pipeline execution events into a user-friendly narrative timeline using event sourcing architecture.

## Overview

The Narrator is an observer layer that answers:
- What is the agent doing right now?
- What did we learn in this stage?
- How does this connect to the research goal?

```
Research Pipeline → Raw Events → Narrator → Timeline Events → SSE → UI
```

## Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Research Pipeline (GPU pods)                                 │
│ Emits execution events via webhooks                         │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Webhook Endpoints                                           │
│ server/app/api/research_pipeline_events.py                 │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Narrator Service                                            │
│ ├─ event_handlers.py    - Transform raw → timeline events  │
│ ├─ state_reducer.py     - Compute state from events        │
│ └─ narrator_service.py  - Orchestrate persistence          │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL                                                  │
│ ├─ rp_timeline_events       - Append-only event log        │
│ └─ rp_research_run_state    - Computed state (JSONB)       │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ SSE Stream                                                  │
│ server/app/api/research_runs_narrative.py                  │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Frontend (Braided + React)                                  │
│ frontend/src/features/narrator/                            │
└─────────────────────────────────────────────────────────────┘
```

## Design Principles

**Event Sourcing**  
Timeline events are immutable source of truth. State is computed from events via pure reducers.

**Symmetric Schemas**  
Pydantic models (backend) generate TypeScript types (frontend) automatically. Frontend and backend cannot drift.

**Separation of Concerns**  
- Backend: Event transformation, state computation, business logic
- Frontend: Rendering only, no state computation

**Resource Management**  
Braided manages SSE connections and Zustand store lifecycle independently from React component lifecycle.

## How It Works

### Event Flow

1. **Pipeline emits raw event** via webhook
2. **Event handler transforms** raw event → timeline event
3. **Timeline event persisted** to `rp_timeline_events` table
4. **State reducer computes** new state from current state + event
5. **New state persisted** to `rp_research_run_state` table
6. **SSE publishes** timeline event and state update
7. **Frontend receives** and renders

### Example: Stage Progress Event

```python
# 1. Pipeline sends webhook
POST /api/research-pipeline/stage-progress
{
  "run_id": "rp-abc123",
  "stage": "1_initial_implementation",
  "iteration": 3,
  "total_iterations": 10,
  "metric": 0.823
}

# 2. Event handler transforms
def handle_stage_progress(run_id, event_data):
    if event_data["iteration"] == 1:
        return StageStartedEvent(...)
    return ProgressUpdateEvent(...)

# 3. Reducer updates state
def handle_progress_update(state, event):
    return StateUpdateResult(changes={
        "timeline": state.timeline + [event],
        "current_stage": event.stage,
        "overall_progress": event.iteration / event.total_iterations,
    })

# 4. State persisted with optimistic locking
UPDATE rp_research_run_state 
SET state_data = $1, version = version + 1
WHERE run_id = $2 AND version = $3

# 5. SSE streams update
yield f"event: timeline_event\n"
yield f"data: {json.dumps(event)}\n\n"

# 6. Frontend updates store
narratorStore.addEvents([event])
```

## Backend Components

### Event Handlers (`event_handlers.py`)

Transform raw execution events → timeline events.

```python
EVENT_HANDLERS = {
    "stage_progress": handle_stage_progress,
    "substage_completed": handle_substage_completed,
    "running_code": handle_code_execution,
    "paper_generation_progress": handle_paper_generation,
}

def handle_stage_progress(run_id: str, event_data: Dict) -> Optional[TimelineEvent]:
    # Logic to create StageStartedEvent or ProgressUpdateEvent
    # Returns None if event should be skipped
```

### State Reducer (`state_reducer.py`)

Pure function that computes new state from current state + event.

```python
def reduce(state: ResearchRunState, event: TimelineEvent) -> StateUpdateResult:
    """
    Pure function: (state, event) → state changes
    No side effects, deterministic, testable
    """
    handler = HANDLERS.get(event.type)
    if not handler:
        return StateUpdateResult(changes={})
    return handler(state, event)

def handle_stage_started(state, event):
    return StateUpdateResult(changes={
        "timeline": state.timeline + [event],
        "current_stage": event.stage,
        "status": "running",
    })
```

### Narrator Service (`narrator_service.py`)

Orchestrates event ingestion and state updates.

```python
async def ingest_narration_event(db, run_id, event_type, event_data):
    # 1. Transform raw → timeline event
    timeline_event = process_execution_event(run_id, event_type, event_data)
    if not timeline_event:
        return
    
    # 2. Persist event
    await db.insert_timeline_event(run_id, timeline_event)
    
    # 3. Update state
    current_state = await db.get_research_run_state(run_id) or create_initial_state(run_id)
    result = reduce(current_state, timeline_event)
    new_state = apply_changes(current_state, result.changes)
    
    # 4. Persist state with optimistic locking
    await db.upsert_research_run_state(run_id, new_state, current_version=current_state.version)
```

## Frontend Components

### Braided Resources

Manages SSE connections and Zustand store lifecycle separately from React.

```typescript
// System configuration
export const systemConfig = {
  narratorStore: narratorStoreResource,  // Zustand store wrapper
  sseStream: sseStreamResource,          // SSE connection manager
  cleanup: cleanupResource,              // Shutdown coordinator
};

export const narrativeSystemManager = createSystemManager(systemConfig);
export const { useResource } = createSystemHooks(narrativeSystemManager);
```

**Why Braided?**
- Separates resource management from React component lifecycle
- Automatic cleanup prevents memory leaks
- Resources can depend on each other
- Testable in isolation without React

### SSE Stream Resource

Manages SSE connection with automatic reconnection and event batching.

```typescript
const handlers: EventHandlers = {
  timeline_event: (data: TimelineEvent) => {
    state.accumulatedEvents.push(data);
    debouncedCommit.notify(); // Batch every 200ms
  },
  state_snapshot: (data: ResearchRunState) => {
    narratorStore.setResearchState(data);
  },
};
```

### Narrator Store Resource

Zustand store wrapper for ResearchRunState. Receives state from backend, no computation.

```typescript
interface NarratorStore {
  state: ResearchRunState | null;
  setResearchState: (state: ResearchRunState) => void;
  addEvents: (events: TimelineEvent[]) => void;
  reset: () => void;
}
```

### React UI

Renders timeline events by stage. No business logic, just presentation.

```typescript
function TimelineView() {
  const { state } = useResource("narratorStore");
  const eventsByStage = groupEventsByStage(state.timeline);
  
  return (
    <div>
      {eventsByStage.map(stage => (
        <StageSection key={stage.stageId} stage={stage} />
      ))}
    </div>
  );
}
```

## Database Schema

### `rp_timeline_events`

Immutable event log (append-only).

```sql
CREATE TABLE rp_timeline_events (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL,
    event_id        TEXT UNIQUE NOT NULL,
    event_type      TEXT NOT NULL,
    event_data      JSONB NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    stage           TEXT,
    node_id         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rp_timeline_events_run_id ON rp_timeline_events(run_id);
CREATE INDEX idx_rp_timeline_events_run_timestamp ON rp_timeline_events(run_id, timestamp);
```

**Query examples:**
```sql
-- Get all timeline events for a run
SELECT * FROM rp_timeline_events 
WHERE run_id = 'rp-abc123' 
ORDER BY timestamp;

-- Get events by type
SELECT * FROM rp_timeline_events 
WHERE run_id = 'rp-abc123' AND event_type = 'node_result'
ORDER BY timestamp;
```

### `rp_research_run_state`

Computed state snapshot for fast access.

```sql
CREATE TABLE rp_research_run_state (
    run_id          TEXT PRIMARY KEY,
    state_data      JSONB NOT NULL,
    version         BIGINT NOT NULL DEFAULT 1,
    last_event_id   TEXT,
    updated_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**State structure:**
```json
{
  "run_id": "rp-abc123",
  "status": "running",
  "current_stage": "2_baseline_tuning",
  "overall_progress": 0.35,
  "timeline": [...],
  "stages": {
    "1_initial_implementation": {
      "status": "completed",
      "summary": "Established baseline...",
      "best_node_id": "node-123"
    }
  },
  "version": 42,
  "updated_at": "2026-01-20T03:45:12Z"
}
```

## Event Types

Production run `rp-73eb061b43` (7.5 hours, 244 timeline events):

| Event Type | Count | Purpose |
|------------|-------|---------|
| `node_execution_started` | 68 | Track node starts |
| `node_execution_completed` | 68 | Track node completions |
| `node_result` | 66 | Results and metrics |
| `progress_update` | 16 | Stage iteration progress |
| `paper_generation_step` | 14 | Paper writing steps |
| `stage_started` | 5 | Stage boundaries |
| `stage_completed` | 5 | Stage summaries |
| `run_started` | 1 | Run initialization |
| `run_finished` | 1 | Run completion |

All event schemas defined in `server/app/models/timeline_events.py`.

## Production Performance

Run `rp-73eb061b43` analysis:
- Duration: 7.5 hours
- Timeline events: 244 (11.6% of 2,108 total events)
- High-signal events: 45%
- Event insertion: <5ms
- State reconstruction: <50ms
- SSE streaming: 0 dropped events

Codex events (1,487) intentionally kept separate to avoid timeline pollution. Available in `rp_codex_events` table for debugging.

## Quick Start

### Query Timeline
```sql
SELECT 
    event_type,
    event_data->>'headline' as headline,
    timestamp,
    stage
FROM rp_timeline_events 
WHERE run_id = 'YOUR_RUN_ID'
ORDER BY timestamp;
```

### Query Current State
```sql
SELECT 
    state_data->>'current_stage' as stage,
    state_data->>'overall_progress' as progress,
    state_data->>'status' as status
FROM rp_research_run_state 
WHERE run_id = 'YOUR_RUN_ID';
```

### Access UI
Navigate to `/research-run/{id}/narrative`

## Key Files

### Backend
- `server/app/models/timeline_events.py` - Event schemas
- `server/app/models/narrator_state.py` - State schema
- `server/app/services/narrator/event_handlers.py` - Event transformation
- `server/app/services/narrator/state_reducer.py` - State computation
- `server/app/services/narrator/narrator_service.py` - Orchestration
- `server/app/api/research_pipeline_events.py` - Webhooks
- `server/app/api/research_runs_narrative.py` - SSE endpoint

### Frontend
- `frontend/src/features/narrator/systems/narrative.ts` - Braided system
- `frontend/src/features/narrator/systems/resources/sseStream.ts` - SSE management
- `frontend/src/features/narrator/systems/resources/narratorStore.ts` - Store
- `frontend/src/features/narrator/components/timeline/TimelineView.tsx` - UI

### Database
- `database_migrations/versions/0034_narrator_timeline_tables.py` - Schema

### Documentation
- `docs/narrator/extending.md` - How to add events and debug issues
- `.regibyte/narrator-architecture/analysis/event-analysis.md` - Production analysis
- `.regibyte/narrator-architecture/analysis/codex-integration-decision.md` - Design decisions

## Next Steps

See `extending.md` for:
- Adding new timeline events
- Debugging common issues
- Operations and monitoring
- Known issues and workarounds
