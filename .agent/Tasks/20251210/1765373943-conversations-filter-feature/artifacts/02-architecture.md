# Architecture: Conversations Filtering Feature

## Overview

This document defines the architecture for adding server-side filtering to the `/conversations` endpoint, allowing users to filter by conversation status and research run status using toggle buttons.

---

## Data Flow Diagram

```
+------------------+     +-------------------+     +------------------+
|  ConversationsPage |-->| DashboardContext  |-->| ConversationsLayout |
|                    |   |  (filter state)   |   |  (API calls)        |
+------------------+     +-------------------+     +------------------+
         |                        |                        |
         v                        v                        v
+------------------+     +-------------------+     +------------------+
| IdeationQueueHeader |  | loadConversations()|  | apiFetch()        |
| (toggle buttons)    |  | builds query string|  | /conversations?... |
+------------------+     +-------------------+     +------------------+
                                                           |
                                                           v
                                               +------------------+
                                               | FastAPI Endpoint  |
                                               | GET /conversations|
                                               +------------------+
                                                           |
                                                           v
                                               +------------------+
                                               | list_conversations|
                                               | (dynamic WHERE)   |
                                               +------------------+
                                                           |
                                                           v
                                               +------------------+
                                               | PostgreSQL        |
                                               | conversations +   |
                                               | research_pipeline |
                                               | _runs JOIN        |
                                               +------------------+
```

---

## API Contract Changes

### GET /conversations

**Current Parameters:**
- `limit: int = 100`
- `offset: int = 0`

**New Parameters:**
- `conversation_status: Optional[str] = None` - Filter by conversation status
- `run_status: Optional[str] = None` - Filter by research run status

**Valid Values:**
- `conversation_status`: `"draft"` | `"with_research"` (validated against `CONVERSATION_STATUSES`)
- `run_status`: `"pending"` | `"running"` | `"failed"` | `"completed"` (validated against `PIPELINE_RUN_STATUSES`)

**Behavior:**
- When `conversation_status` is omitted or empty: No conversation status filter applied
- When `run_status` is omitted or empty: No run status filter applied
- When both filters provided: AND logic (intersection)
- When `run_status` is provided: Only returns conversations with at least one matching run

**Example Requests:**
```
GET /conversations?limit=100&offset=0
GET /conversations?conversation_status=draft
GET /conversations?run_status=completed
GET /conversations?conversation_status=with_research&run_status=running
```

---

## Database Query Changes

### Current Query (simplified)
```sql
SELECT c.*, iv.title, iv.abstract, ...
FROM conversations c
LEFT JOIN users u ON c.imported_by_user_id = u.id
LEFT JOIN ideas i ON i.conversation_id = c.id
LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id
WHERE c.imported_by_user_id = $user_id
ORDER BY c.updated_at DESC
LIMIT $limit OFFSET $offset
```

### Updated Query (with filters)
```sql
SELECT DISTINCT c.*, iv.title, iv.abstract, ...
FROM conversations c
LEFT JOIN users u ON c.imported_by_user_id = u.id
LEFT JOIN ideas i ON i.conversation_id = c.id
LEFT JOIN idea_versions iv ON i.active_idea_version_id = iv.id
LEFT JOIN research_pipeline_runs rpr ON rpr.idea_id = i.id  -- Only when run_status provided
WHERE c.imported_by_user_id = $user_id
  AND c.status = $conversation_status                        -- Only when conversation_status provided
  AND rpr.status = $run_status                               -- Only when run_status provided
ORDER BY c.updated_at DESC
LIMIT $limit OFFSET $offset
```

**Key Changes:**
1. Add conditional `LEFT JOIN research_pipeline_runs` when `run_status` is provided
2. Add `WHERE c.status = %s` when `conversation_status` is provided
3. Add `WHERE rpr.status = %s` when `run_status` is provided
4. Add `DISTINCT` to SELECT when joining runs table (one conversation may have multiple runs)

---

## Component Hierarchy

```
ConversationsLayout (state owner)
    |
    +-- DashboardContext.Provider (provides filter state + API)
            |
            +-- ConversationsPage
                    |
                    +-- IdeationQueueHeader (renders toggle buttons)
                    |       |
                    |       +-- Conversation Status Toggles (inline, not a separate component)
                    |       +-- Run Status Toggles (inline, not a separate component)
                    |
                    +-- IdeationQueueList
```

---

## Type Definitions

### New Types (conversation-filter.types.ts)

```typescript
/**
 * Conversation status filter options for API query
 * 'all' = no filter applied (omit param from request)
 */
export type ConversationStatusFilter = 'all' | 'draft' | 'with_research';

/**
 * Run status filter options for API query
 * 'all' = no filter applied (omit param from request)
 */
export type RunStatusFilter = 'all' | 'pending' | 'running' | 'completed' | 'failed';

/**
 * Filter configuration for toggle buttons (OCP-compliant)
 */
export interface FilterConfig {
  label: string;
  activeClass: string;
}
```

### New Config (conversation-filter-utils.ts)

```typescript
import type { ConversationStatusFilter, RunStatusFilter, FilterConfig } from '../types/conversation-filter.types';

export const CONVERSATION_STATUS_OPTIONS: ConversationStatusFilter[] = ['all', 'draft', 'with_research'];

export const CONVERSATION_STATUS_FILTER_CONFIG: Record<ConversationStatusFilter, FilterConfig> = {
  all: { label: 'All', activeClass: 'bg-slate-500/15 text-slate-300' },
  draft: { label: 'Draft', activeClass: 'bg-amber-500/15 text-amber-400' },
  with_research: { label: 'With Research', activeClass: 'bg-emerald-500/15 text-emerald-400' },
};

export const RUN_STATUS_OPTIONS: RunStatusFilter[] = ['all', 'pending', 'running', 'completed', 'failed'];

export const RUN_STATUS_FILTER_CONFIG: Record<RunStatusFilter, FilterConfig> = {
  all: { label: 'All', activeClass: 'bg-slate-500/15 text-slate-300' },
  pending: { label: 'Pending', activeClass: 'bg-amber-500/15 text-amber-400' },
  running: { label: 'Running', activeClass: 'bg-sky-500/15 text-sky-400' },
  completed: { label: 'Completed', activeClass: 'bg-emerald-500/15 text-emerald-400' },
  failed: { label: 'Failed', activeClass: 'bg-red-500/15 text-red-400' },
};
```

---

## Context Changes (DashboardContext)

### Interface Extension

```typescript
interface DashboardContextType {
  // Existing
  conversations: Conversation[];
  isLoading: boolean;
  selectConversation: (conversation: Conversation) => void;
  refreshConversations: () => Promise<void>;
  sortKey: SortKey;
  setSortKey: (key: SortKey) => void;
  sortDir: SortDir;
  setSortDir: (dir: SortDir) => void;

  // New filter state
  conversationStatusFilter: ConversationStatusFilter;
  setConversationStatusFilter: (filter: ConversationStatusFilter) => void;
  runStatusFilter: RunStatusFilter;
  setRunStatusFilter: (filter: RunStatusFilter) => void;
}
```

---

## Implementation Order

### Phase 1: Backend (T001, T002)
1. **T001**: Add query params to `GET /conversations` endpoint
   - Add `conversation_status: Optional[str] = None` parameter
   - Add `run_status: Optional[str] = None` parameter
   - Add validation against `CONVERSATION_STATUSES` and `PIPELINE_RUN_STATUSES`
   - Pass filters to `db.list_conversations()`

2. **T002**: Update `list_conversations()` database method
   - Add `conversation_status: Optional[str] = None` parameter
   - Add `run_status: Optional[str] = None` parameter
   - Add conditional LEFT JOIN for `research_pipeline_runs`
   - Build WHERE clause dynamically
   - Add DISTINCT when joining runs table

### Phase 2: Frontend Types/Config (T003)
3. **T003**: Create filter types and config
   - Create `conversation-filter.types.ts` with type definitions
   - Create `conversation-filter-utils.ts` with config objects

### Phase 3: Frontend State (T005, T006)
4. **T005**: Update `DashboardContext` interface
   - Add filter state types to interface
   - Export new types

5. **T006**: Update `ConversationsLayout`
   - Add useState for `conversationStatusFilter` and `runStatusFilter`
   - Update `loadConversations` to build query string with filters
   - Add filter state and setters to context value
   - Add useEffect to refetch when filters change

### Phase 4: Frontend UI (T004, T007)
6. **T004**: Update `IdeationQueueHeader`
   - Add filter props to interface
   - Add toggle button groups (inline, using pattern from IdeationQueueFilters)
   - Import and use new filter configs

7. **T007**: Update `ConversationsPage`
   - Get filter state from `useDashboard()`
   - Pass filter props to `IdeationQueueHeader`

---

## SOLID Compliance

### SRP (Single Responsibility)
- **Types file**: Only type definitions
- **Utils file**: Only config objects and helper functions
- **Context**: Only state management interface
- **Layout**: Only state management and API calls
- **Page**: Only composition and rendering
- **Header**: Only UI rendering

### OCP (Open/Closed)
- Filter configs use `Record<FilterOption, FilterConfig>` pattern
- New filters can be added by extending config, not modifying code
- Same pattern already proven in `STATUS_FILTER_CONFIG` and `LOG_FILTER_CONFIG`

### LSP (Liskov Substitution)
- All filter types extend from base `FilterConfig` interface
- Any filter config can be used with the same toggle button pattern

### ISP (Interface Segregation)
- `IdeationQueueHeaderProps` extended minimally (only filter props needed)
- Filter props are optional to maintain backward compatibility
- Context interface remains focused on dashboard concerns

### DIP (Dependency Inversion)
- Components depend on types/interfaces, not concrete implementations
- Filter configs injected via props, not hardcoded
- API calls abstracted through `apiFetch` utility

---

## Reusable Assets Summary

| Asset | Usage |
|-------|-------|
| `IdeationQueueFilters.tsx` pattern | Copy inline toggle button pattern |
| `STATUS_FILTER_CONFIG` pattern | Follow for new filter configs |
| `cn()` utility | Class merging for toggle state |
| `CONVERSATION_STATUSES` | Validation in API endpoint |
| `PIPELINE_RUN_STATUSES` | Validation in API endpoint |
| `list_conversations` query pattern | Extend with WHERE clauses |
| `apiFetch` | API calls with query strings |
| `convertApiConversationList` | No changes needed |

---

## Files Summary

### Files to Create (2)
1. `frontend/src/features/conversation/types/conversation-filter.types.ts`
2. `frontend/src/features/conversation/utils/conversation-filter-utils.ts`

### Files to Extend (6)
1. `server/app/api/conversations.py` - Add query params
2. `server/app/services/database/conversations.py` - Update query
3. `frontend/src/features/dashboard/contexts/DashboardContext.tsx` - Add types
4. `frontend/src/app/(dashboard)/conversations/layout.tsx` - Add state
5. `frontend/src/features/conversation/components/IdeationQueueHeader.tsx` - Add UI
6. `frontend/src/app/(dashboard)/conversations/page.tsx` - Wire props

---

## Edge Cases

1. **No matching results**: Show empty state message
2. **Run status on conversations with no runs**: Returns no results (expected)
3. **Invalid status values**: Return 400 Bad Request with error message
4. **Both filters active**: AND logic, narrowest result set
5. **Pagination with filters**: Filters applied before pagination

---

## Testing Considerations

### Backend Tests
- Test each filter independently
- Test combined filters
- Test invalid filter values
- Test pagination with filters
- Test empty result sets

### Frontend Tests
- Test filter state changes trigger API call
- Test toggle button accessibility (aria-pressed)
- Test count updates after filtering
- Test empty state rendering
