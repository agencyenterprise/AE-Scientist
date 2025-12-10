# Conversations Filter Feature - Product Requirements Document

## Overview

Add server-side filtering capabilities to the `/conversations` page to allow users to filter conversations by conversation status and research run status. This feature will use toggle buttons for an intuitive filtering experience and leverage server-side filtering for improved performance with large datasets.

## Status

**Current Phase:** Planning
**See:** `task.json` for detailed status and decisions

---

## User Stories

### Story 1: Filter by Conversation Status

**As a** logged-in user
**I want** to filter conversations by their status (draft or with research)
**So that** I can quickly find conversations that are ready for research runs versus those still in draft

**Acceptance Criteria:**
- [ ] Toggle buttons displayed for conversation status: "All", "Draft", "With Research"
- [ ] Only one status can be selected at a time (single-select toggle group)
- [ ] Default selection is "All" (no filter applied)
- [ ] Filter is applied server-side via API query parameter
- [ ] Results update immediately when a filter is selected
- [ ] Loading state shown while fetching filtered results
- [ ] Filter selection persists during the session (not across page refreshes for MVP)

**Technical Tasks:**
1. Add `conversation_status` query parameter to `GET /conversations` endpoint
2. Update `list_conversations` database method to support status filtering
3. Create `ConversationStatusFilterToggle` component with toggle buttons
4. Update `IdeationQueueHeader` to include the filter toggle
5. Update `useDashboard` context or create new hook to support filtered fetching
6. Wire up filter state to trigger API refetch with new parameters

---

### Story 2: Filter by Research Run Status

**As a** logged-in user
**I want** to filter conversations by their research run status (pending, running, completed, failed)
**So that** I can find conversations with specific run outcomes (e.g., see all completed research, or find failed runs to retry)

**Acceptance Criteria:**
- [ ] Toggle buttons displayed for run status: "All", "Pending", "Running", "Completed", "Failed"
- [ ] Only one run status can be selected at a time
- [ ] Default selection is "All" (no filter applied)
- [ ] Filter is applied server-side via API query parameter
- [ ] Only shows conversations that have at least one run matching the status
- [ ] Conversations with no runs are hidden when any run status filter (except "All") is selected
- [ ] Results update immediately when a filter is selected
- [ ] Loading state shown while fetching filtered results

**Technical Tasks:**
1. Add `run_status` query parameter to `GET /conversations` endpoint
2. Update `list_conversations` database query to join with research_pipeline_runs and filter by run status
3. Create `RunStatusFilterToggle` component with toggle buttons
4. Update `IdeationQueueHeader` to include the run status filter toggle
5. Ensure both filters can be combined (e.g., "With Research" + "Completed")

---

### Story 3: Combined Filter Experience

**As a** logged-in user
**I want** to combine conversation status and run status filters
**So that** I can narrow down results precisely (e.g., show only conversations with completed research runs)

**Acceptance Criteria:**
- [ ] Both filter toggles visible and usable simultaneously
- [ ] Filters are combined with AND logic on the server
- [ ] Count display updates to show filtered count vs total count
- [ ] Clear visual indication of active filters
- [ ] "All" option in each filter group clears that specific filter
- [ ] Empty state shown when no conversations match the combined filters

**Technical Tasks:**
1. API accepts both `conversation_status` and `run_status` parameters simultaneously
2. Database query applies both filters with AND logic
3. UI shows both filter groups in a clean, organized layout
4. Update count display in header to reflect filtered results

---

## Requirements

### Functional Requirements

1. **Server-Side Filtering**: All filtering must happen on the server to handle large datasets efficiently
2. **Toggle Button UI**: Use toggle buttons (not dropdowns) per acceptance criteria
3. **Single Selection**: Each filter group allows only one selection at a time
4. **Combined Filters**: Both filters can be active simultaneously (AND logic)
5. **Real-Time Updates**: Results update immediately when filters change
6. **Persistent Count**: Display "Showing X of Y conversations" to indicate filtering is active

### Non-Functional Requirements

1. **Performance**: Filtering should complete within 500ms for typical datasets
2. **Accessibility**: Toggle buttons must be keyboard navigable and screen reader friendly
3. **Responsive**: Filter controls should work on mobile viewports
4. **Consistency**: Follow existing design system patterns for buttons and layouts

### API Contract

```
GET /conversations?limit=100&offset=0&conversation_status=draft&run_status=completed

Query Parameters:
- limit (int): Maximum results (default: 100, max: 1000)
- offset (int): Pagination offset (default: 0)
- conversation_status (string, optional): Filter by conversation status
  - Values: "draft", "with_research"
  - Default: null (no filter)
- run_status (string, optional): Filter by research run status
  - Values: "pending", "running", "completed", "failed"
  - Default: null (no filter)

Response: ConversationListResponse (unchanged structure)
```

---

## Technical Decisions

See `task.json` `decisions` array for full list.

### Key Decisions:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Filter Location | Server-side | Better performance for large datasets, reduces client memory usage |
| UI Component | Toggle buttons | Per acceptance criteria; provides clear visual feedback |
| Filter Logic | AND combination | Most intuitive for users narrowing results |
| State Management | URL params + React state | Enables shareable filter URLs in future |

---

## Reusability Analysis

### Existing Assets to REUSE

| Asset | Location | Usage |
|-------|----------|-------|
| `Button` component | `frontend/src/shared/components/ui/button.tsx` | Base for toggle buttons (use `variant="outline"` + active state) |
| `useConversationsFilter` hook | `frontend/src/features/conversation/hooks/useConversationsFilter.ts` | Extend to support server-side filtering params |
| `IdeationQueueHeader` component | `frontend/src/features/conversation/components/IdeationQueueHeader.tsx` | Add filter toggles to existing header |
| `StatusFilterOption` type | `frontend/src/features/conversation/types/ideation-queue.types.ts` | Extend for new filter types |
| `ConversationsMixin` | `server/app/services/database/conversations.py` | Add filtering to `list_conversations` method |
| Design guidelines | `.agent/System/design-guidelines.md` | Use `.btn-filter` pattern for toggle buttons |

### Similar Features to Reference

| Feature | Location | Learnings |
|---------|----------|-----------|
| Research Runs List filters | `server/app/services/database/research_pipeline_runs.py:list_all_research_pipeline_runs` | Pattern for adding filter params to list queries |
| Status types | `frontend/src/features/conversation/types/ideation-queue.types.ts` | Existing `IdeaStatus` and `ConversationStatus` type definitions |

---

## Implementation Plan

### Phase 1: Backend API Changes
- [ ] Update `GET /conversations` to accept `conversation_status` and `run_status` query params
- [ ] Update `list_conversations` in `ConversationsMixin` to filter by status
- [ ] Add JOIN with `research_pipeline_runs` for run status filtering
- [ ] Add integration tests for new filter parameters

### Phase 2: Frontend Filter Components
- [ ] Create `FilterToggleGroup` component for reusable toggle button groups
- [ ] Create `ConversationStatusFilter` component
- [ ] Create `RunStatusFilter` component
- [ ] Add CSS styles following `.btn-filter` pattern from design guidelines

### Phase 3: Integration
- [ ] Extend or create hook for server-filtered conversations fetching
- [ ] Update `IdeationQueueHeader` to include filter components
- [ ] Update `ConversationsPage` to manage filter state and trigger refetches
- [ ] Update count display to show filtered vs total

### Phase 4: Polish
- [ ] Add loading states during filter changes
- [ ] Add empty state for no matching results
- [ ] Test keyboard navigation and accessibility
- [ ] Test responsive layout on mobile

---

## File Structure (Proposed)

### Files to Modify

**Backend:**
- `server/app/api/conversations.py` - Add query params to `list_conversations` route
- `server/app/services/database/conversations.py` - Update `list_conversations` method with filters

**Frontend:**
- `frontend/src/features/conversation/components/IdeationQueueHeader.tsx` - Add filter toggles
- `frontend/src/features/conversation/hooks/useConversationsFilter.ts` - Extend for server-side filtering
- `frontend/src/features/conversation/types/ideation-queue.types.ts` - Add new filter types
- `frontend/src/app/(dashboard)/conversations/page.tsx` - Wire up filter state
- `frontend/src/features/dashboard/contexts/DashboardContext.tsx` - May need to support filter params

### Files to Create

**Frontend:**
- `frontend/src/features/conversation/components/FilterToggleGroup.tsx` - Reusable toggle button group
- `frontend/src/features/conversation/components/ConversationFilters.tsx` - Container for both filter groups

---

## Related Documentation

- `.agent/README.md` - Documentation index
- `.agent/System/project_architecture.md` - Overall architecture
- `.agent/System/frontend_architecture.md` - Frontend patterns
- `.agent/System/design-guidelines.md` - UI patterns (especially Filter Buttons section)
- `.agent/SOP/server_api_routes.md` - How to add API parameters
- `.agent/SOP/frontend_features.md` - Component organization
