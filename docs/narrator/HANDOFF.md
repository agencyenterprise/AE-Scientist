# Narrator System Handoff

## What Is This?

The Narrator system transforms technical research pipeline execution into a user-friendly narrative timeline using event sourcing architecture.

## Documentation

Two files, everything you need:

**`README.md`** - Architecture  
What it is, how it works, components, database schema, performance metrics, quick start.

**`extending.md`** - Operations  
How to add events, integrate new data, operate in production, debug issues, known issues.

## Quick Start

```bash
# Query timeline
SELECT event_type, event_data->>'headline', timestamp
FROM rp_timeline_events 
WHERE run_id = 'YOUR_RUN_ID'
ORDER BY timestamp;

# Check state
SELECT state_data->>'status', state_data->>'current_stage'
FROM rp_research_run_state 
WHERE run_id = 'YOUR_RUN_ID';

# Access UI
/research-run/{id}/narrative
```

## Key Concepts

**Event Sourcing:** Timeline events (immutable) → State (computed via reducer)

**Symmetric Schemas:** Pydantic (backend) → TypeScript (frontend), auto-generated

**Resource Management:** Braided manages SSE connections and stores independently from React

## Architecture

```
Pipeline → Webhooks → Event Handlers → Timeline Events (DB)
                                     ↓
                          State Reducer → Research State (DB)
                                     ↓
                          SSE Stream → Frontend (Braided + React)
```

## Key Files

**Backend:**
- `server/app/services/narrator/event_handlers.py` - Raw → Timeline transformation
- `server/app/services/narrator/state_reducer.py` - State computation (pure functions)
- `server/app/services/narrator/narrator_service.py` - Orchestration
- `server/app/models/timeline_events.py` - Event schemas
- `server/app/api/research_runs_narrative.py` - SSE endpoint

**Frontend:**
- `frontend/src/features/narrator/systems/narrative.ts` - Braided system
- `frontend/src/features/narrator/systems/resources/sseStream.ts` - SSE management
- `frontend/src/features/narrator/components/timeline/` - UI components

**Database:**
- `rp_timeline_events` - Event log (append-only)
- `rp_research_run_state` - State snapshot (JSONB)

## Production Metrics

From run `rp-73eb061b43`:
- Duration: 7.5 hours
- Timeline events: 244
- Event insertion: <5ms
- State reconstruction: <50ms
- SSE streaming: 0 dropped events

## Known Limitations

1. **Best node reasoning** - Data exists (66 events/run) but not in timeline yet. See extending.md for integration guide.

2. **Artifacts** - Uploaded (15/run) but not shown in timeline. See extending.md for integration guide.

3. **Codex events** - 1,487 per run intentionally kept separate (would 7x timeline size). Available in `rp_codex_events` for debugging.

4. **Token usage** - Available in Codex events but not displayed. Can be added, see extending.md.

All limitations documented with implementation paths in `extending.md`.

## Support

**Need to understand the system?** → Read `README.md`

**Need to add features or debug?** → Read `extending.md`

Both docs are self-contained. No need to jump between files.

## Technical Decisions

**Why event sourcing?**  
State can be rebuilt from events. Time-travel debugging. Audit trail.

**Why Braided?**  
Separates resource lifecycle from React. Prevents memory leaks. Testable in isolation.

**Why separate Codex events?**  
1,487 low-value events (bash commands) would pollute 244 high-signal timeline events.

## Next Steps

1. **Add best node reasoning** - Follow guide in `extending.md`, data already exists
2. **Add artifacts** - Follow guide in `extending.md`, straightforward integration
3. **Extract token usage** - For LLM cost tracking, data in Codex events

All have complete implementation guides in `extending.md`.

---

Everything you need is in `README.md` and `extending.md`. Production-validated, ready to extend.
