# Initial Context

## Agent
feature-planner

## Source
User request via orchestrator

## Task Type
Feature Enhancement

## Timestamp
2025-12-05 (created by feature-planner agent)

## Original Request

Enhance the Ideation Queue (currently called "Conversations") to display multiple research runs per idea.

### User Requirements

From the Ideation Queue (currently called "Conversations") you should be able to click into ideas which have run through the full pipeline and see the artifacts created from prior "runs" of that "idea".

Each "conversation" may be associated with multiple "research runs" - you should from the Ideation Queue tab be able to see for each "idea" a list of all the "research runs" associated with that idea, and be able to click into each one

Clicking should take you to the "Research" tab for that "research run" so you can see from that research run all of the artifacts and the full log which was created when that idea was run

If an idea is currently in progress i.e. actively being run, that should be clear from the Ideation Queue page i.e. research runs underneath an idea should be marked as "complete" / "failed" / "in progress"

Currently you can only see some text summarizing the idea, not the more detailed history of research attempted on that idea

## Context from Orchestrator

This is an **EXPANSION** of the existing ideation-queue-enhancement feature. The base implementation is already complete (showing idea cards with status badges). Now we need to:

1. Display research runs as nested items under each idea card
2. Show status for each research run (complete/failed/in progress)
3. Make research runs clickable to navigate to the Research tab
4. Ensure the UI clearly shows which research runs belong to which idea

## Related Documentation

- `.agent/Tasks/ideation-queue-enhancement/PRD.md` - Original ideation queue enhancement (completed)
- `.agent/System/frontend_architecture.md` - Frontend patterns and conventions
- `.agent/System/server_architecture.md` - Backend API structure

## Key Technical Findings (from pre-planning research)

### Backend Already Supports This

1. **Database method exists**: `list_research_runs_for_conversation(conversation_id)` in `/server/app/services/database/research_pipeline_runs.py`

2. **API already returns research runs**: `GET /api/conversations/{id}` returns `ConversationResponse` which includes:
   ```json
   {
     "research_runs": [
       {
         "run_id": "rp-xxx",
         "status": "pending|running|failed|completed",
         "idea_id": 123,
         "idea_version_id": 456,
         "gpu_type": "...",
         "cost": 0.0,
         "created_at": "...",
         "updated_at": "..."
       }
     ]
   }
   ```

3. **Research detail page exists**: `/research/[runId]` page displays full run details with artifacts and logs

### Frontend Current State

1. **Ideation Queue page** (`/conversations/page.tsx`): Uses `IdeationQueueCard` for each idea
2. **Research runs not fetched**: The conversations list endpoint does NOT include research runs
3. **Navigation to research detail**: Route is `/research/{runId}`

### Gap Analysis

| Aspect | Current State | Required |
|--------|---------------|----------|
| Conversations list | Returns conversations without research runs | Need to fetch runs per conversation |
| Card display | Shows idea title/abstract/status | Need to show nested research runs |
| Run status | N/A | Show pending/running/completed/failed badges |
| Navigation | Click card -> conversation detail | Click run -> research detail page |
| Real-time updates | No SSE for list | Consider polling or SSE for in-progress runs |

## Initial Assessment

**Complexity**: Moderate
- Backend support exists, primarily a frontend enhancement
- Need to handle expandable/collapsible cards or always-visible nested runs
- Must maintain performance with potentially many runs per conversation
