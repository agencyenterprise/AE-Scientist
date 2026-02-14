# Extending & Operating the Narrator

Guide for adding timeline events, debugging issues, and operating in production.

## Table of Contents

1. [Adding New Timeline Events](#adding-new-timeline-events)
2. [Adding Integration Points](#adding-integration-points)
3. [Operations](#operations)
4. [Debugging](#debugging)
5. [Known Issues](#known-issues)

## Adding New Timeline Events

Example: Add Best Node Selected event to show LLM reasoning when best node changes.

Data source: `rp_best_node_reasoning_events` table (66 events per run).

### Step 1: Define Event Schema

**File:** `server/app/models/timeline_events.py`

```python
class BestNodeSelectedEvent(TimelineEventBase):
    """Emitted when best node changes with LLM reasoning"""
    
    type: Literal["best_node_selected"] = "best_node_selected"
    
    headline: str
    node_id: str
    reasoning: str
    previous_best_id: Optional[str] = None
    new_metric: Optional[float] = None
    previous_metric: Optional[float] = None
    improvement: Optional[float] = None

# Add to union
TimelineEvent = Annotated[
    Union[
        RunStartedEvent,
        StageStartedEvent,
        BestNodeSelectedEvent,  # ADD
        # ...
    ],
    Field(discriminator="type"),
]
```

### Step 2: Create Event Handler

**File:** `server/app/services/narrator/event_handlers.py`

```python
def handle_best_node_selection(run_id: str, event_data: Dict) -> Optional[TimelineEvent]:
    node_id = event_data.get("selected_node_id")
    reasoning = event_data.get("reasoning", "")
    
    if not node_id or not reasoning:
        return None
    
    # Calculate improvement
    new_metric = event_data.get("metric")
    prev_metric = event_data.get("previous_best_metric")
    improvement = None
    if new_metric is not None and prev_metric is not None:
        improvement = new_metric - prev_metric
    
    headline = f"New best node selected"
    if improvement and improvement > 0:
        headline += f" (+{improvement*100:.1f}%)"
    
    return BestNodeSelectedEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        stage=event_data.get("stage", ""),
        node_id=node_id,
        headline=headline,
        reasoning=reasoning,
        previous_best_id=event_data.get("previous_best_id"),
        new_metric=new_metric,
        previous_metric=prev_metric,
        improvement=improvement,
    )

# Register
EVENT_HANDLERS = {
    # ...
    "best_node_selection": handle_best_node_selection,
}
```

### Step 3: Add Reducer Handler

**File:** `server/app/services/narrator/state_reducer.py`

```python
def handle_best_node_selected(state: ResearchRunState, event: BestNodeSelectedEvent) -> StateUpdateResult:
    return StateUpdateResult(changes={
        "timeline": state.timeline + [event],
        "current_best_node_id": event.node_id,
        "updated_at": datetime.utcnow(),
        f"stages.{event.stage}.best_node_id": event.node_id,
        f"stages.{event.stage}.best_metric": event.new_metric,
    })

# Register
HANDLERS = {
    # ...
    "best_node_selected": handle_best_node_selected,
}
```

### Step 4: Wire to Webhook (if new raw event)

**File:** `server/app/api/research_pipeline_events.py`

```python
@router.post("/best-node-selection")
async def ingest_best_node_selection(
    payload: BestNodeSelectionPayload,
    db: DatabaseManager = Depends(get_database),
):
    # Store raw event (optional)
    await db.insert_best_node_reasoning_event(
        run_id=payload.run_id,
        stage=payload.stage,
        reasoning=payload.reasoning,
        selected_node_id=payload.selected_node_id,
    )
    
    # Send to narrator
    await ingest_narration_event(
        db,
        run_id=payload.run_id,
        event_type="best_node_selection",
        event_data=payload.dict(),
    )
    
    return {"status": "ok"}
```

For existing event tables, query during state reconstruction or migration.

### Step 5: Generate TypeScript Types

```bash
cd frontend
npm run generate-types
```

### Step 6: Add UI Component

**File:** `frontend/src/features/narrator/components/timeline/BestNodeCard.tsx`

```typescript
export function BestNodeCard({ event }: { event: BestNodeSelectedEvent }) {
  return (
    <div className="border-l-4 border-green-500 pl-4 py-2">
      <h4 className="font-semibold">{event.headline}</h4>
      <p className="text-sm text-gray-600 mt-1">{event.reasoning}</p>
      {event.improvement && event.improvement > 0 && (
        <div className="mt-2 text-sm text-green-600">
          +{(event.improvement * 100).toFixed(1)}% improvement
        </div>
      )}
    </div>
  );
}

// Wire to timeline
function EventCard({ event }: { event: TimelineEvent }) {
  switch (event.type) {
    case "best_node_selected":
      return <BestNodeCard event={event} />;
    // ...
  }
}
```

### Step 7: Test

```python
# Test handler
def test_handle_best_node_selection():
    event_data = {
        "stage": "1_initial_implementation",
        "selected_node_id": "node-123",
        "reasoning": "Best accuracy",
        "metric": 0.823,
        "previous_best_metric": 0.756,
    }
    result = handle_best_node_selection("run-abc", event_data)
    assert result.type == "best_node_selected"
    assert result.improvement > 0

# Test reducer
def test_reducer_best_node_selected():
    state = create_initial_state("run-abc")
    event = BestNodeSelectedEvent(...)
    result = handle_best_node_selected(state, event)
    new_state = apply_changes(state, result.changes)
    assert new_state.current_best_node_id == "node-123"
```

## Adding Integration Points

Example: Integrate artifact uploads to show plots/data in timeline.

### Define Event Schema

```python
class ArtifactGeneratedEvent(TimelineEventBase):
    type: Literal["artifact_generated"] = "artifact_generated"
    headline: str
    filename: str
    file_type: str
    description: Optional[str] = None
    generating_node_id: Optional[str] = None
```

### Option A: Real-time (on upload)

```python
@router.post("/artifacts/upload")
async def upload_artifact(file: UploadFile, run_id: str, ...):
    # ... existing upload logic ...
    
    if is_important_artifact(file.filename):
        await ingest_narration_event(
            db,
            run_id=run_id,
            event_type="artifact_uploaded",
            event_data={
                "filename": file.filename,
                "file_type": file.content_type,
                "source_path": source_path,
            }
        )
```

### Option B: Retroactive (query table)

```python
async def rebuild_state_from_events(db, run_id):
    # ... existing event replay ...
    
    # Add artifact events from table
    artifacts = await db.get_artifacts(run_id)
    for artifact in artifacts:
        if is_important_artifact(artifact.filename):
            event = create_artifact_event(artifact)
            # Insert into timeline
```

### Filter Important Artifacts

```python
def is_important_artifact(filename: str) -> bool:
    """Show plots and data, not configs"""
    important_extensions = ['.png', '.jpg', '.npy', '.pt', '.pdf']
    
    if 'config' in filename.lower():
        return False
    
    return any(filename.endswith(ext) for ext in important_extensions)
```

### Extract Context from Path

```python
def extract_artifact_context(source_path: str) -> Dict[str, Any]:
    """Extract stage/node from artifact path"""
    context = {"stage": None, "node_id": None, "description": None}
    
    # Parse stage
    stage_match = re.search(r'stage_(\w+)', source_path)
    if stage_match:
        context["stage"] = stage_match.group(1)
    
    # Parse node
    node_match = re.search(r'node_([a-f0-9]+)', source_path)
    if node_match:
        context["node_id"] = node_match.group(1)
    
    # Generate description
    filename = os.path.basename(source_path)
    if 'plot' in filename:
        context["description"] = "Generated visualization"
    elif '.npy' in filename:
        context["description"] = "Experiment data"
    
    return context
```

## Operations

### Monitor Events

```sql
-- Events per run
SELECT run_id, COUNT(*) as event_count
FROM rp_timeline_events
GROUP BY run_id
ORDER BY event_count DESC
LIMIT 10;

-- Event type distribution
SELECT event_type, COUNT(*) as count
FROM rp_timeline_events
GROUP BY event_type
ORDER BY count DESC;

-- Events per stage
SELECT stage, COUNT(*) as count
FROM rp_timeline_events
WHERE run_id = 'YOUR_RUN_ID'
GROUP BY stage
ORDER BY MIN(timestamp);
```

### Monitor State

```sql
-- State update frequency
SELECT 
    run_id,
    version,
    updated_at,
    updated_at - LAG(updated_at) OVER (PARTITION BY run_id ORDER BY version) as time_since_last
FROM rp_research_run_state
ORDER BY updated_at DESC
LIMIT 20;

-- Current state
SELECT 
    run_id,
    state_data->>'status' as status,
    state_data->>'current_stage' as stage,
    state_data->>'overall_progress' as progress,
    version
FROM rp_research_run_state
ORDER BY updated_at DESC
LIMIT 10;
```

### Performance

```sql
-- Event insertion latency
SELECT 
    event_type,
    AVG(EXTRACT(EPOCH FROM (created_at - timestamp))) as avg_latency_seconds
FROM rp_timeline_events
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY event_type
ORDER BY avg_latency_seconds DESC;
```

### Logs

```bash
grep "Narrator:" server.log
grep "Narrator: Processing event" server.log
grep "Narrator: Error" server.log
```

## Debugging

### Timeline Events Not Appearing

**Check raw events arriving:**
```sql
SELECT COUNT(*) FROM rp_run_stage_progress_events WHERE run_id = 'YOUR_RUN_ID';
SELECT COUNT(*) FROM rp_substage_completed_events WHERE run_id = 'YOUR_RUN_ID';
```

**Check timeline events created:**
```sql
SELECT COUNT(*) FROM rp_timeline_events WHERE run_id = 'YOUR_RUN_ID';
```

**Test handler in isolation:**
```python
from app.services.narrator.event_handlers import handle_stage_progress

event_data = {
    "stage": "1_initial_implementation",
    "iteration": 1,
    "total_iterations": 10,
}
result = handle_stage_progress("test-run", event_data)
print(result)
```

### State Not Updating

**Check timeline events exist:**
```sql
SELECT COUNT(*) FROM rp_timeline_events WHERE run_id = 'YOUR_RUN_ID';
```

**Check state version:**
```sql
SELECT version, updated_at FROM rp_research_run_state WHERE run_id = 'YOUR_RUN_ID';
-- Version should increment with each event
```

**Test reducer:**
```python
from app.services.narrator.state_reducer import reduce

state = ResearchRunState.create_initial("test-run")
event = StageStartedEvent(...)
result = reduce(state, event)
print(result.changes)
```

**Check for version conflicts:**
```bash
grep "version conflict" server.log
```

### SSE Connection Issues

**Check endpoint:**
```bash
curl http://localhost:8000/api/research-runs/YOUR_RUN_ID/narrative-stream
```

**Check browser console for errors**

**Check frontend connection:**
```typescript
console.log("SSE state:", eventSource.readyState);
// 0 = CONNECTING, 1 = OPEN, 2 = CLOSED
```

### Frontend Not Rendering

**Check events in store:**
```typescript
const { state } = useResource("narratorStore");
console.log("Timeline events:", state.timeline.length);
```

**Test selectors:**
```typescript
import { groupEventsByStage } from '@/features/narrator/lib/narratorSelectors';
const grouped = groupEventsByStage(state.timeline);
console.log("Grouped stages:", grouped);
```

## Known Issues

### 1. Duplicate Node Execution Events

**Symptom:** Same `execution_id` appearing 2-3 times

**Example:**
```
node_execution_completed (0.0s) - 21:40:22
node_execution_completed (77.2s) - 21:42:12  ← Same execution_id
node_execution_completed (72.8s) - 21:44:28  ← Same execution_id
```

**Cause:** Codex execution spawns multiple runfile executions

**Current workaround:** Deduplicate by execution_id + run_type in handler

### 2. Best Node Reasoning Not in Timeline

**Status:** Data exists in `rp_best_node_reasoning_events` (66 per run), not yet integrated

**Solution:** Follow "Adding New Timeline Events" guide above

### 3. Artifacts Not in Timeline

**Status:** `artifact_generated` event not yet implemented

**Solution:** Follow "Adding Integration Points" guide above

### 4. React Duplicate Key Warnings

**Fixed:** Filter empty stages and add fallback keys

**Location:** `frontend/src/features/narrator/lib/narratorSelectors.ts` + `TimelineView.tsx`

### 5. Codex Events Not Integrated

**Status:** Intentional - 1,487 Codex events per run kept separate to avoid timeline pollution (would increase from 244 to 1,731 events)

**Decision:** See `.regibyte/narrator-architecture/analysis/codex-integration-decision.md`

**Available data:**
- Token usage in `turn.completed` events
- Command executions in `item.started/completed`
- Available in `rp_codex_events` table for debugging

**Query Codex events:**
```sql
SELECT * FROM rp_codex_events 
WHERE run_id = 'YOUR_RUN_ID'
ORDER BY created_at;

-- Token usage
SELECT 
    stage,
    event_content->'usage' as token_usage,
    created_at
FROM rp_codex_events
WHERE run_id = 'YOUR_RUN_ID'
  AND event_type = 'turn.completed'
ORDER BY created_at;
```

**Potential enhancement:** Extract token usage for cost tracking

### 7. Token Usage Not Visible in UI

**Status:** Data exists but not shown

**To integrate:**
1. Create `LLMCostUpdateEvent` schema
2. Handle `turn.completed` events
3. Extract: `input_tokens`, `cached_input_tokens`, `output_tokens`
4. Calculate cost, display in timeline

**Production data:** Average 1.1M input tokens per turn, 90% cache rate, 4-25K output tokens

### 8. Optimistic Locking Conflicts

**Frequency:** <0.1% of updates

**Symptoms:**
```
ERROR: UPDATE failed - version conflict
Expected version: 42
Actual version: 43
```

**Workaround:** Retry with exponential backoff (already implemented)

**If frequency increases:** Batch state updates or queue events for sequential processing

## Quick Reference

```bash
# Enable narrator
export ENABLE_NARRATOR=true

# Check timeline
SELECT event_type, COUNT(*) FROM rp_timeline_events WHERE run_id = ? GROUP BY event_type;

# Check state
SELECT state_data->>'status', version FROM rp_research_run_state WHERE run_id = ?;
```

```python
# Rebuild state
from app.services.narrator.narrator_service import rebuild_state_from_events
state = await rebuild_state_from_events(db, "run-abc123")

# Test handler
from app.services.narrator.event_handlers import EVENT_HANDLERS
handler = EVENT_HANDLERS["stage_progress"]
result = handler("run-abc", {"stage": "1_initial_implementation", ...})

# Test reducer
from app.services.narrator.state_reducer import reduce
result = reduce(current_state, timeline_event)
```

## Related Documentation

- `README.md` - Architecture overview