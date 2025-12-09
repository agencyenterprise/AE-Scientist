# Planning Phase

## Agent
feature-planner

## Timestamp
2025-12-05

## Input Received
- Context: User request via orchestrator for Ideation Queue research runs enhancement
- Project docs consulted:
    - .agent/README.md
    - .agent/System/project_architecture.md
    - .agent/System/frontend_architecture.md
    - .agent/System/server_architecture.md
    - .agent/System/orchestrator_architecture.md
    - .agent/Tasks/ideation-queue-enhancement/PRD.md

## Reasoning

### Why This Approach

**Expand-on-Demand Pattern Selected**

After analyzing the codebase, I recommend an expand-on-demand approach where research runs are fetched when the user clicks to expand a card, rather than loading all runs upfront. This is because:

1. **Backend already supports it**: The `GET /api/conversations/{id}` endpoint already returns `research_runs` in the response, so no backend changes are needed.

2. **Performance**: Loading runs for all conversations on initial page load would be expensive. Users may have many ideas but only care about runs for specific ones.

3. **Existing pattern**: The app already uses similar patterns (e.g., loading conversation details on click).

4. **React Query caching**: Once fetched, runs are cached, so subsequent expansions are instant.

**Alternative Considered but Rejected**

Modifying the `/api/conversations` list endpoint to include runs was considered but rejected because:
- Requires backend changes
- Would significantly increase response payload
- Most users won't need runs for all conversations simultaneously

### Pattern Selection

- **Chose pattern**: Feature-based component organization with hooks for data fetching
- **Because**: Consistent with existing codebase structure (`features/conversation/`)
- **Reference**: `features/research/hooks/useRecentResearch.ts` for React Query pattern

### Dependencies Identified

1. **IdeationQueueCard.tsx**: Base component to modify - will add expandable section
2. **ConversationResponse type**: Already includes `research_runs` array in API types
3. **Research run status patterns**: Can reuse from `research-utils.tsx`
4. **date-fns / formatRelativeTime**: Already available in shared utils

### Risks & Considerations

| Risk | Mitigation |
|------|------------|
| Performance with many runs per card | Limit display to 5 most recent, with "View all" link |
| Race conditions on rapid expand/collapse | React Query handles this automatically |
| Stale run status data | Add 30s stale time, user can manually refresh |
| Navigation conflict (card click vs run click) | Use event.stopPropagation() on run clicks |
| Mobile layout complexity | Stack runs vertically, simplify info displayed |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data fetching | On-demand per card | Reduces initial load, backend already supports detail endpoint |
| UI pattern | Expandable card section | Keeps list scannable, shows runs only when needed |
| Status badges | Reuse research feature patterns | Consistency across app |
| Navigation | Click run -> /research/{runId} | Existing route, no new pages needed |
| Backend changes | None required | ConversationResponse already has research_runs |
| Runs display limit | Show max 5 recent | Performance, with "View all" option |

## Output Summary

- PRD created: `.agent/Tasks/ideation-queue-research-runs/PRD.md`
- Files to create: 3 frontend files (2 new components, 1 new hook)
- Files to modify: 3 frontend files (types, utils, card component)
- Estimated complexity: **Moderate** - primarily frontend work, backend ready

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `features/conversation/components/IdeationQueueRunItem.tsx` | Single research run display row |
| `features/conversation/components/IdeationQueueRunsList.tsx` | Container for runs with loading/empty states |
| `features/conversation/hooks/useConversationResearchRuns.ts` | React Query hook to fetch runs |

### Modified Files

| File | Changes |
|------|---------|
| `features/conversation/types/ideation-queue.types.ts` | Add RunStatus type, props interfaces |
| `features/conversation/utils/ideation-queue-utils.tsx` | Add getRunStatusBadge() function |
| `features/conversation/components/IdeationQueueCard.tsx` | Add expandable runs section |
| `features/conversation/index.ts` | Export new components and hooks |

## For Next Phase (Architecture)

Key considerations for the architect:

1. **Component Structure**: Should runs be a collapsible section or always visible? Current recommendation is expandable to reduce visual noise.

2. **Type Alignment**: Need to verify frontend types match `ResearchRunSummary` from backend models.

3. **Click Handler Separation**: The card click (-> conversation detail) vs run click (-> research detail) needs clear implementation to prevent bubbling issues.

4. **Loading States**: Consider skeleton UI while runs are being fetched.

5. **Error Handling**: What to show if run fetch fails? Recommend inline error with retry button.

6. **Cache Strategy**: Decide on stale time for research runs (recommended: 30 seconds for running, longer for completed).

## Approval Status
- [ ] Pending approval
- [ ] Approved - proceed to Architecture
- [ ] Modified - see feedback below

### Feedback (if modified)
{User feedback will be added here}
