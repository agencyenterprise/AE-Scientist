# Stage 5: Paper Generation & Review - Product Requirements Document

## Overview

Add **Stage 5: Paper Generation & Review** to the research pipeline UI. This stage provides real-time progress tracking for post-Stage-4 operations that currently run silently for 30-60 minutes.

**Problem:** After Stage 4 completes, users see nothing while paper generation and review runs.

**Solution:** Add granular progress tracking for four sub-steps:
- Plot Aggregation
- Citation Gathering
- Paper Writeup
- Paper Review

## Status

| Phase | Status | Agent |
|-------|--------|-------|
| Classification | Completed | task-classifier |
| Planning | In Progress | feature-planner |
| Analysis | Pending | codebase-analyzer |
| Architecture | Pending | feature-architecture-expert |
| Tech Guidance | Pending | fastapi-expert, nextjs-expert |
| Implementation | Pending | feature-executor |
| Documentation | Pending | documentation-reviewer |

See `task.json` for full state.

---

## Technical Approach

Follow the **same pattern** as existing stage progress events (stages 1-4):

1. New DB table `rp_paper_generation_events`
2. Pipeline writes to table AND sends webhook to server
3. Server stores events and broadcasts via SSE
4. Frontend fetches events and displays in UI

---

## Requirements

### Functional Requirements

1. **Progress Tracking** - Display real-time progress for each sub-step of paper generation
2. **Sub-step Visibility** - Show individual progress for:
   - Plot Aggregation (reflection count, figure count)
   - Citation Gathering (round progress, citations found)
   - Paper Writeup (current substep, reflection count)
   - Paper Review (reviews completed, partial scores)
3. **Overall Progress** - Calculate weighted Stage 5 overall progress
4. **Initial Load** - Fetch historical events when user opens run detail page
5. **Real-time Updates** - Stream new events via SSE during active runs

### Non-Functional Requirements

1. **Pattern Consistency** - Must follow existing stage progress event patterns exactly
2. **Backward Compatibility** - Must not break existing stage 1-4 progress tracking
3. **Performance** - Events should be lightweight and not impact pipeline execution
4. **Reliability** - Best-effort event persistence (failures should not crash pipeline)

---

## Technical Decisions

See `task.json` `decisions` array for full list with rationale.

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Implementation Order | Bottom-up (DB -> Backend -> Server -> Frontend) | Each layer depends on previous layer's interfaces |
| Pattern Source | Follow existing `rp_run_stage_progress_events` pattern | Ensures consistency and maintainability |
| User Stories | Skip | Technical infrastructure following established patterns |
| Webhook Location | `research_pipeline_events.py` | Consistency with existing webhook endpoints |

---

## Reusability Analysis

### Existing Assets to REUSE

| Asset | Location | How to Reuse |
|-------|----------|--------------|
| Database migration pattern | `server/database_migrations/versions/0004_rp_event_tables.py` | Copy structure for new table |
| Event base class | `research_pipeline/ai_scientist/treesearch/events.py` | Inherit from `BaseEvent` |
| Event persistence | `research_pipeline/ai_scientist/telemetry/event_persistence.py` | Add new event kind handling |
| Webhook pattern | `server/app/api/research_pipeline_events.py` | Add new endpoint |
| Database service mixin | `server/app/services/database/rp_events.py` | Add new NamedTuple and methods |
| SSE hook | `frontend/src/features/research/hooks/useResearchRunSSE.ts` | Add new event type handler |
| Stage component | `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | Extend with Stage 5 |

### Similar Features to Reference

| Feature | What to Learn |
|---------|---------------|
| Stage Progress Events | Exact pattern to follow for DB, events, persistence, server, frontend |
| Substage Completed Events | How to handle JSONB summary field |

---

## Implementation Plan

### Phase 1: Database Migration

**File:** `server/database_migrations/versions/XXXX_rp_paper_generation_events.py`

Create table:
```sql
CREATE TABLE rp_paper_generation_events (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    step TEXT NOT NULL,            -- "plot_aggregation", "citation_gathering", "paper_writeup", "paper_review"
    substep TEXT,                  -- e.g. "reflection_2", "compiling", "llm_review"
    progress FLOAT NOT NULL,       -- 0.0 to 1.0 (overall Stage 5 progress)
    step_progress FLOAT NOT NULL,  -- 0.0 to 1.0 (current step progress)
    details JSONB,                 -- step-specific: {citations_found: 15, figure_count: 8, scores: {...}}
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_rp_paper_gen_events_run ON rp_paper_generation_events(run_id);
```

### Phase 2: Backend Event Infrastructure

**Files to modify:**
- `research_pipeline/ai_scientist/treesearch/events.py` - Add `PaperGenerationProgressEvent` class
- `research_pipeline/ai_scientist/telemetry/event_persistence.py` - Add persistence + webhook path

Key changes:
1. Update `EventKind` Literal to include `"paper_generation_progress"`
2. Add `PaperGenerationProgressEvent` dataclass with `persistence_record()` method
3. Add webhook path to `WebhookClient._EVENT_PATHS`
4. Add `_insert_paper_generation_progress()` method to `EventPersistenceManager`

### Phase 3: Pipeline Event Emission

**Files to modify:**
- `research_pipeline/launch_scientist_bfts.py` - Add `event_callback` to post-Stage-4 functions
- `research_pipeline/ai_scientist/perform_plotting.py` - Emit events in `aggregate_plots()`
- `research_pipeline/ai_scientist/perform_writeup.py` - Emit events in `gather_citations()`, `perform_writeup()`
- `research_pipeline/ai_scientist/perform_llm_review.py` - Emit events in `perform_review()`

### Phase 4: Server

**Files to modify:**
- `server/app/api/research_pipeline_events.py` - Add POST webhook endpoint (NOT research_pipeline_runs.py)
- `server/app/services/database/rp_events.py` - Add `PaperGenerationEvent` NamedTuple and `list_paper_generation_events()` method
- `server/app/api/research_pipeline_runs.py` - Update SSE endpoint to include paper generation events

### Phase 5: Frontend

**Files to modify:**
- `frontend/src/types/research.ts` - Add `PaperGenerationEvent` type
- `frontend/src/features/research/hooks/useResearchRunSSE.ts` - Handle new event type

**Files to create:**
- `frontend/src/features/research/hooks/usePaperGenerationProgress.ts` - Fetch hook for initial load
- `frontend/src/features/research/components/run-detail/paper-generation-progress.tsx` - Stage 5 UI component

---

## Progress Calculation

Stage 5 overall progress = weighted average of sub-steps:

| Sub-step | Weight | Rationale |
|----------|--------|-----------|
| Plot Aggregation | 15% | Quick setup phase |
| Citation Gathering | 15% | Variable length but bounded |
| Paper Writeup | 50% | Core work, multiple reflections |
| Paper Review | 20% | Final validation |

Example: If plot=100%, citations=100%, writeup=50%, review=0%
Overall = (0.15 x 1.0) + (0.15 x 1.0) + (0.50 x 0.5) + (0.20 x 0.0) = **55%**

---

## File Structure (Proposed)

```
server/
  database_migrations/versions/
    0017_rp_paper_generation_events.py      # NEW
  app/
    api/
      research_pipeline_events.py            # MODIFY (add webhook)
      research_pipeline_runs.py              # MODIFY (add SSE + GET)
    services/database/
      rp_events.py                           # MODIFY (add methods)

research_pipeline/
  ai_scientist/
    treesearch/
      events.py                              # MODIFY (add event class)
    telemetry/
      event_persistence.py                   # MODIFY (add persistence)
    perform_plotting.py                      # MODIFY (emit events)
    perform_writeup.py                       # MODIFY (emit events)
    perform_llm_review.py                    # MODIFY (emit events)
  launch_scientist_bfts.py                   # MODIFY (pass callback)

frontend/
  src/
    types/
      research.ts                            # MODIFY (add type)
    features/research/
      hooks/
        useResearchRunSSE.ts                 # MODIFY (handle event)
        usePaperGenerationProgress.ts        # NEW
      components/run-detail/
        research-pipeline-stages.tsx         # MODIFY (add Stage 5)
        paper-generation-progress.tsx        # NEW
```

---

## Validation Findings

After reviewing the existing codebase, the plan is **valid and comprehensive** with the following clarifications:

### Confirmed Patterns

1. **Database migration** - Uses SQLAlchemy `op.create_table()` with explicit column definitions
2. **Event class** - Frozen dataclass inheriting from `BaseEvent` with `persistence_record()` method
3. **Webhook client** - Uses `_EVENT_PATHS` dict mapping event kind to URL path
4. **Database service** - Uses NamedTuple for return types with `psycopg2.extras.RealDictCursor`
5. **SSE endpoint** - Polls database in async generator loop, no pub/sub

### Corrections to Original Plan

| Item | Original Plan | Corrected |
|------|---------------|-----------|
| Webhook file | `research_pipeline_runs.py` | Should be `research_pipeline_events.py` for consistency |
| Migration number | `0017` | Verify current head - may need different number |

### Additional Considerations

1. **SSE Initial Data** - The SSE endpoint sends initial data including all event types. Need to add paper generation events to this initial payload.
2. **GET Endpoint** - May want a dedicated GET endpoint for paper generation events (like existing `list_stage_progress_events`)
3. **Frontend State** - The `ResearchRunDetails` type and SSE hook state need updates for new event type

---

## Related Documentation

- `.agent/System/server_architecture.md` - Server patterns and conventions
- `.agent/System/frontend_architecture.md` - Frontend patterns and conventions
- `.agent/SOP/server_database_migrations.md` - Migration procedures
- Source plan: `~/.claude/plans/prancy-foraging-kazoo.md`

---

## Open Questions

1. Should paper generation events be included in the existing `ResearchRunDetailsResponse` or as a separate field?
2. Should the Stage 5 component be integrated into `research-pipeline-stages.tsx` or be a separate component?
3. What is the exact emission frequency during paper writeup reflections?

---

## Approval

This PRD validates the existing plan at `~/.claude/plans/prancy-foraging-kazoo.md`.

**Recommendation:** Proceed with implementation following the corrected file locations noted above.
