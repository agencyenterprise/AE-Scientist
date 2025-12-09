# Reusable Assets Analysis

## Agent
codebase-analyzer

## Timestamp
2025-12-08

## Analysis Summary

Scanned the following areas for reusable code:
- `frontend/src/features/conversation/` - Current ideation queue implementation
- `frontend/src/features/research/` - Research run components and utilities
- `frontend/src/shared/` - Shared utilities, hooks, and UI components
- `frontend/src/types/` - Type definitions including API types

---

## MUST REUSE

These assets are exact matches for our needs - import and use directly.

### 1. Status Badge Function - `getStatusBadge()`

**File**: `/frontend/src/features/research/utils/research-utils.tsx`

**What it does**: Returns a styled React element with status badge for research run statuses (pending, running, completed, failed). Includes icons and proper color coding.

**Import**:
```typescript
import { getStatusBadge } from "@/features/research/utils/research-utils";
```

**Usage**:
```typescript
{getStatusBadge(run.status)} // Returns styled badge JSX
{getStatusBadge(run.status, "sm")} // Small size (default)
{getStatusBadge(run.status, "lg")} // Large size
```

**Why relevant**: Exact match for PRD requirement - status badges with same colors (amber/pending, sky/running, emerald/completed, red/failed). Already includes spinner animation for running state.

---

### 2. Run ID Truncation - `truncateRunId()`

**File**: `/frontend/src/features/research/utils/research-utils.tsx`

**What it does**: Truncates long run IDs with ellipsis (default 14 chars).

**Import**:
```typescript
import { truncateRunId } from "@/features/research/utils/research-utils";
```

**Usage**:
```typescript
truncateRunId("rp-abc123def456") // Returns "rp-abc123def4..."
```

**Why relevant**: PRD specifies showing truncated run IDs like "rp-abc123..."

---

### 3. Relative Time Formatting - `formatRelativeTime()`

**File**: `/frontend/src/shared/lib/date-utils.ts`

**What it does**: Formats ISO date strings as relative time (e.g., "2 hours ago").

**Import**:
```typescript
import { formatRelativeTime } from "@/shared/lib/date-utils";
```

**Usage**:
```typescript
formatRelativeTime("2024-01-15T10:00:00Z") // Returns "2 hours ago"
```

**Why relevant**: PRD requires showing "Created 2h ago" for research runs. Already used in `IdeationQueueCard`.

---

### 4. API Client - `apiFetch()`

**File**: `/frontend/src/shared/lib/api-client.ts`

**What it does**: Type-safe fetch wrapper with error handling, credentials, and automatic JSON parsing.

**Import**:
```typescript
import { apiFetch } from "@/shared/lib/api-client";
```

**Usage**:
```typescript
const data = await apiFetch<ConversationResponse>(`/conversations/${id}`);
```

**Why relevant**: Required for fetching conversation details (which includes `research_runs`). Handles auth and error states.

---

### 5. Class Utility - `cn()`

**File**: `/frontend/src/shared/lib/utils.ts`

**What it does**: Merges Tailwind CSS classes with clsx and tailwind-merge.

**Import**:
```typescript
import { cn } from "@/shared/lib/utils";
```

**Usage**:
```typescript
className={cn("base-class", isActive && "active-class", className)}
```

**Why relevant**: Standard utility used throughout the codebase for conditional class merging.

---

### 6. Research Run Types - `ResearchRunSummary`

**File**: `/frontend/src/types/api.gen.ts` (auto-generated from OpenAPI)

**What it does**: Type definition for research runs from the `ConversationResponse.research_runs` array.

**Import**:
```typescript
import type { ConversationResponse } from "@/types";
// Access research_runs from ConversationResponse
```

**Schema includes**:
- `run_id: string` - Unique identifier
- `status: string` - "pending" | "running" | "completed" | "failed"
- `gpu_type?: string | null` - GPU type used
- `created_at: string` - ISO timestamp
- `updated_at: string` - ISO timestamp
- `error_message?: string | null` - Error details if failed

**Why relevant**: Backend already returns this in `GET /api/conversations/{id}`. Use directly without creating new types.

---

### 7. Lucide Icons (Already in project)

**Package**: `lucide-react`

**Icons to use**:
- `Clock` - For timestamps
- `Cpu` - For GPU type display
- `ChevronDown` / `ChevronUp` - For expand/collapse
- `ExternalLink` or `ArrowRight` - For "View" action

**Import**:
```typescript
import { Clock, Cpu, ChevronDown, ArrowRight } from "lucide-react";
```

**Why relevant**: Consistent icon usage throughout the app. Already used in IdeationQueueCard and research components.

---

## CONSIDER REUSING

These assets could be adapted with minor modifications.

### 1. React Query Pattern from `useRecentResearch`

**File**: `/frontend/src/features/research/hooks/useRecentResearch.ts`

**What it does**: Fetches research runs using React Query with proper caching and error handling.

**Pattern to follow**:
```typescript
export function useConversationResearchRuns(conversationId: number, enabled: boolean) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["conversation-research-runs", conversationId],
    queryFn: () => fetchConversationResearchRuns(conversationId),
    staleTime: 30 * 1000, // 30 seconds
    enabled, // Only fetch when expanded
  });
  // ...
}
```

**Why "consider"**: Need to create new hook but follow same pattern exactly. The fetch function needs to call `/api/conversations/{id}` and extract `research_runs`.

---

### 2. Loading Skeleton Pattern from `ResearchHistorySkeleton`

**File**: `/frontend/src/features/research/components/ResearchHistorySkeleton.tsx`

**What it does**: Animated placeholder UI while loading.

**Pattern to follow**:
```typescript
<div className="animate-pulse rounded-lg border border-slate-800 bg-slate-900/50 p-4">
  <div className="h-4 w-20 rounded bg-slate-700/50" />
  {/* More skeleton elements */}
</div>
```

**Why "consider"**: Create simpler inline skeleton for runs list (not a separate component). Use same `animate-pulse` and `bg-slate-700/50` patterns.

---

### 3. Empty State Pattern from `IdeationQueueEmpty`

**File**: `/frontend/src/features/conversation/components/IdeationQueueEmpty.tsx`

**Pattern to follow**:
```typescript
<div className="flex h-16 items-center justify-center">
  <p className="text-sm text-slate-500">No research runs yet</p>
</div>
```

**Why "consider"**: Much simpler empty state needed - just text message, no icon. Follow same text styling.

---

### 4. Card Layout from `ResearchHistoryCard`

**File**: `/frontend/src/features/research/components/ResearchHistoryCard.tsx`

**Relevant patterns**:
- Status badge positioning with title
- Timestamp pill styling
- Hover states for links

**Why "consider"**: The run item will be much simpler (single row), but can borrow the timestamp styling:
```typescript
<span className="inline-flex items-center gap-1 rounded-full border border-slate-800/80 bg-slate-900/70 px-3 py-1 text-[10px] uppercase tracking-[0.3em] text-slate-500">
  <Clock className="h-3 w-3 text-slate-400" />
  {relativeTime}
</span>
```

---

### 5. Link Navigation Pattern from `research-board-card-footer`

**File**: `/frontend/src/features/research/components/research-board-card-footer.tsx`

**Pattern**:
```typescript
<Link
  href={`/research/${runId}`}
  className="inline-flex items-center gap-2 rounded-lg bg-emerald-500/15 px-4 py-2 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/25"
>
  View Details
  <ArrowRight className="h-4 w-4" />
</Link>
```

**Why "consider"**: We need a simpler, smaller link/button. Use same route `/research/${runId}` but lighter styling for nested items.

---

## CREATE NEW

These need to be built from scratch.

### 1. `useConversationResearchRuns` Hook

**Why not reusable**: No existing hook fetches single conversation details for extracting research_runs. The closest (`useRecentResearch`) fetches from `/research-runs/` endpoint, not conversation detail.

**New file**: `frontend/src/features/conversation/hooks/useConversationResearchRuns.ts`

**Responsibilities**:
- Accept `conversationId` and `enabled` flag
- Fetch from `/api/conversations/{id}`
- Extract and return `research_runs` array
- Use React Query with appropriate stale time
- Return loading, error, data states

---

### 2. `IdeationQueueRunItem` Component

**Why not reusable**: No existing component shows a compact single-row research run display. `ResearchHistoryCard` is too large/detailed. `ResearchBoardCardHeader` is close but lacks the row layout needed.

**New file**: `frontend/src/features/conversation/components/IdeationQueueRunItem.tsx`

**Layout**:
```
[Status Badge]  rp-abc123...  |  RTX A4000  |  2 hours ago  | [->]
```

**Props needed**:
- `runId: string`
- `status: string`
- `gpuType: string | null`
- `createdAt: string`
- `onClick?: () => void` (for navigation)

---

### 3. `IdeationQueueRunsList` Component

**Why not reusable**: No existing component handles the expandable runs container with loading/empty states specific to this context.

**New file**: `frontend/src/features/conversation/components/IdeationQueueRunsList.tsx`

**Responsibilities**:
- Accept research runs array
- Show loading skeleton while fetching
- Show empty state if no runs
- Map runs to `IdeationQueueRunItem` components
- Handle expand/collapse state (optional)

---

### 4. Expand/Collapse Integration in `IdeationQueueCard`

**Why not reusable**: The card currently wraps entire content in a `<Link>`. Need to:
- Add expand/collapse button that doesn't navigate
- Conditionally render runs section
- Use `event.stopPropagation()` for run item clicks

**Modify**: `frontend/src/features/conversation/components/IdeationQueueCard.tsx`

---

## Type Definitions Needed

### New types to add to `ideation-queue.types.ts`:

```typescript
/**
 * Research run status for display
 */
export type RunStatus = "pending" | "running" | "completed" | "failed";

/**
 * Props for IdeationQueueRunItem component
 */
export interface IdeationQueueRunItemProps {
  runId: string;
  status: RunStatus;
  gpuType: string | null;
  createdAt: string;
  onClick?: () => void;
}

/**
 * Props for IdeationQueueRunsList component
 */
export interface IdeationQueueRunsListProps {
  conversationId: number;
  isExpanded: boolean;
}

/**
 * Extended card props to support expansion
 */
export interface IdeationQueueCardProps {
  id: number;
  title: string;
  abstract: string | null;
  status: IdeaStatus;
  createdAt: string;
  updatedAt: string;
  researchRunsCount?: number; // Optional: show badge with count
}
```

---

## API Adapter Needed

The `ConversationResponse.research_runs` uses snake_case from API. Need to either:

1. **Option A**: Use snake_case directly (simpler, matches existing pattern in `useResearchRunDetails`)
2. **Option B**: Add converter to `api-adapters.ts` for camelCase consistency

**Recommendation**: Option A - use snake_case as returned from API since this is a nested type that won't be used widely.

---

## Summary

| Category | Count | Details |
|----------|-------|---------|
| **MUST REUSE** | 7 | getStatusBadge, truncateRunId, formatRelativeTime, apiFetch, cn, ResearchRunSummary type, Lucide icons |
| **CONSIDER REUSING** | 5 | React Query pattern, skeleton pattern, empty state pattern, card layout patterns, Link navigation |
| **CREATE NEW** | 4 | useConversationResearchRuns hook, IdeationQueueRunItem, IdeationQueueRunsList, Card expand/collapse |

---

## Critical Dependencies

Before implementation, verify:

1. **Backend response structure**: Confirm `GET /api/conversations/{id}` returns `research_runs` array
2. **Type generation**: Ensure `ResearchRunSummary` type in `api.gen.ts` is up to date
3. **Route exists**: Confirm `/research/[runId]` page handles the navigation correctly

---

## Next Steps

1. **Architect** should design the component composition and state management
2. **Executor** should implement in order:
   - Types first
   - Hook second
   - Components third
   - Card modification last
