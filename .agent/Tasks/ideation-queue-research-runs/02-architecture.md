# Architecture Design

## Agent
feature-architecture-expert

## Timestamp
2025-12-08

## Overview

This document defines the architecture for displaying research runs within the Ideation Queue. The design follows SOLID principles and leverages maximum reusability from existing assets.

---

## 1. Component Hierarchy Diagram

```
ConversationsPage
    |
    +-- IdeationQueueHeader (existing, unchanged)
    |
    +-- IdeationQueueList (existing, unchanged)
            |
            +-- IdeationQueueCard (MODIFIED)
                    |
                    +-- [existing card content]
                    |
                    +-- IdeationQueueRunsList (NEW)
                            |
                            +-- [loading skeleton] OR
                            +-- [empty state] OR
                            +-- IdeationQueueRunItem (NEW) [0..n]
```

---

## 2. File Structure

### New Files

| File Path | Purpose |
|-----------|---------|
| `frontend/src/features/conversation/components/IdeationQueueRunItem.tsx` | Single research run display row |
| `frontend/src/features/conversation/components/IdeationQueueRunsList.tsx` | Container with loading/empty states |
| `frontend/src/features/conversation/hooks/useConversationResearchRuns.ts` | React Query hook to fetch runs |

### Modified Files

| File Path | Changes |
|-----------|---------|
| `frontend/src/features/conversation/types/ideation-queue.types.ts` | Add RunStatus type, new props interfaces |
| `frontend/src/features/conversation/components/IdeationQueueCard.tsx` | Add expand/collapse, integrate runs list |
| `frontend/src/features/conversation/index.ts` | Export new components and hook |

### Unchanged Files (Reuse As-Is)

| File Path | What We Reuse |
|-----------|---------------|
| `frontend/src/features/research/utils/research-utils.tsx` | `getStatusBadge()`, `truncateRunId()` |
| `frontend/src/shared/lib/date-utils.ts` | `formatRelativeTime()` |
| `frontend/src/shared/lib/api-client.ts` | `apiFetch()` |
| `frontend/src/shared/lib/utils.ts` | `cn()` |
| `frontend/src/types/api.gen.ts` | `ResearchRunSummary` via `ConversationResponse` |

---

## 3. Component Specifications

### 3.1 IdeationQueueCard (MODIFIED)

**File**: `frontend/src/features/conversation/components/IdeationQueueCard.tsx`

**Purpose**: Display a single idea card with expandable research runs section.

**Responsibility Changes**:
- Current: Renders idea info, wraps in Link for navigation
- New: Renders idea info, manages expand/collapse state, renders runs list conditionally

**Props Interface** (extended):
```typescript
export interface IdeationQueueCardProps {
  id: number;
  title: string;
  abstract: string | null;
  status: IdeaStatus;
  createdAt: string;
  updatedAt: string;
  // NEW: Optional count for showing badge before expand
  researchRunsCount?: number;
}
```

**State Management**:
```typescript
// Local state for expand/collapse
const [isExpanded, setIsExpanded] = useState(false);
```

**Key Implementation Notes**:
1. Remove outer `<Link>` wrapper - card body remains clickable but uses `onClick` with `router.push()`
2. Add expand/collapse button in footer (separate click zone)
3. When expanded, render `<IdeationQueueRunsList conversationId={id} />`
4. Use `event.stopPropagation()` on expand button and run items to prevent card navigation

**Dependencies**:
```typescript
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronUp, Clock } from "lucide-react";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { cn } from "@/shared/lib/utils";
import { getIdeaStatusBadge } from "../utils/ideation-queue-utils";
import { IdeationQueueRunsList } from "./IdeationQueueRunsList";
import type { IdeationQueueCardProps } from "../types/ideation-queue.types";
```

---

### 3.2 IdeationQueueRunsList (NEW)

**File**: `frontend/src/features/conversation/components/IdeationQueueRunsList.tsx`

**Purpose**: Container component that fetches and displays research runs for a conversation.

**Responsibility**:
- Trigger data fetching when rendered (expanded)
- Display loading skeleton while fetching
- Display empty state if no runs
- Map runs to `IdeationQueueRunItem` components

**Props Interface**:
```typescript
export interface IdeationQueueRunsListProps {
  conversationId: number;
}
```

**State Management**:
- No local state - delegates to React Query via `useConversationResearchRuns`

**Component Structure**:
```typescript
export function IdeationQueueRunsList({ conversationId }: IdeationQueueRunsListProps) {
  const { runs, isLoading, error } = useConversationResearchRuns(conversationId);

  // Loading state
  if (isLoading) {
    return <RunsListSkeleton />;
  }

  // Error state
  if (error) {
    return <RunsListError message={error} />;
  }

  // Empty state
  if (!runs || runs.length === 0) {
    return <RunsListEmpty />;
  }

  // Runs list (limit to 5 most recent, show "View all" if more)
  const displayRuns = runs.slice(0, 5);
  const hasMore = runs.length > 5;

  return (
    <div className="mt-3 border-t border-slate-800 pt-3">
      <div className="space-y-2">
        {displayRuns.map((run) => (
          <IdeationQueueRunItem
            key={run.run_id}
            runId={run.run_id}
            status={run.status}
            gpuType={run.gpu_type}
            createdAt={run.created_at}
          />
        ))}
      </div>
      {hasMore && <ViewAllLink conversationId={conversationId} totalCount={runs.length} />}
    </div>
  );
}
```

**Dependencies**:
```typescript
import { useConversationResearchRuns } from "../hooks/useConversationResearchRuns";
import { IdeationQueueRunItem } from "./IdeationQueueRunItem";
```

---

### 3.3 IdeationQueueRunItem (NEW)

**File**: `frontend/src/features/conversation/components/IdeationQueueRunItem.tsx`

**Purpose**: Display a single research run as a compact, clickable row.

**Responsibility**:
- Render run ID (truncated), status badge, GPU type, and relative time
- Handle click to navigate to `/research/{runId}`
- Prevent click bubbling to parent card

**Props Interface**:
```typescript
export interface IdeationQueueRunItemProps {
  runId: string;
  status: string;
  gpuType: string | null;
  createdAt: string;
}
```

**Visual Layout**:
```
+----------------------------------------------------------------------+
| [Status Badge]  rp-abc123...  |  RTX A4000  |  2h ago     [->]       |
+----------------------------------------------------------------------+
```

**Component Structure**:
```typescript
export function IdeationQueueRunItem({
  runId,
  status,
  gpuType,
  createdAt,
}: IdeationQueueRunItemProps) {
  const router = useRouter();

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card navigation
    router.push(`/research/${runId}`);
  };

  return (
    <button
      onClick={handleClick}
      className="flex w-full items-center justify-between gap-3 rounded-lg border border-slate-800/50 bg-slate-900/30 px-3 py-2 text-left transition-colors hover:border-slate-700 hover:bg-slate-800/50"
    >
      <div className="flex items-center gap-3">
        {getStatusBadge(status, "sm")}
        <span className="font-mono text-xs text-slate-400">
          {truncateRunId(runId)}
        </span>
      </div>
      <div className="flex items-center gap-3 text-[10px] text-slate-500">
        {gpuType && <span>{gpuType}</span>}
        <span>{formatRelativeTime(createdAt)}</span>
        <ArrowRight className="h-3 w-3 text-slate-600" />
      </div>
    </button>
  );
}
```

**Dependencies**:
```typescript
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { getStatusBadge, truncateRunId } from "@/features/research/utils/research-utils";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import type { IdeationQueueRunItemProps } from "../types/ideation-queue.types";
```

---

### 3.4 useConversationResearchRuns Hook (NEW)

**File**: `frontend/src/features/conversation/hooks/useConversationResearchRuns.ts`

**Purpose**: Fetch research runs for a specific conversation using React Query.

**Responsibility**:
- Fetch from `/api/conversations/{id}` endpoint
- Extract `research_runs` array from response
- Provide loading, error, and data states
- Cache results appropriately (shorter stale time for running runs)

**Hook Interface**:
```typescript
export interface UseConversationResearchRunsReturn {
  runs: ResearchRunSummary[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useConversationResearchRuns(
  conversationId: number
): UseConversationResearchRunsReturn;
```

**Implementation**:
```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";
import type { ConversationResponse } from "@/types";

// Type alias for the research run summary from API
type ResearchRunSummary = NonNullable<ConversationResponse["research_runs"]>[number];

async function fetchConversationResearchRuns(
  conversationId: number
): Promise<ResearchRunSummary[]> {
  const data = await apiFetch<ConversationResponse>(
    `/conversations/${conversationId}`
  );
  return data.research_runs ?? [];
}

export interface UseConversationResearchRunsReturn {
  runs: ResearchRunSummary[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useConversationResearchRuns(
  conversationId: number
): UseConversationResearchRunsReturn {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["conversation-research-runs", conversationId],
    queryFn: () => fetchConversationResearchRuns(conversationId),
    staleTime: 30 * 1000, // 30 seconds - refresh relatively often for status updates
  });

  return {
    runs: data ?? [],
    isLoading,
    error: error instanceof Error
      ? error.message
      : error
        ? "Failed to fetch research runs"
        : null,
    refetch,
  };
}
```

**Dependencies**:
```typescript
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";
import type { ConversationResponse } from "@/types";
```

---

## 4. Type Definitions

### Additions to `ideation-queue.types.ts`

```typescript
// ============================================================================
// Research Run Types for Ideation Queue Display
// ============================================================================

/**
 * Research run status for display purposes.
 * Matches backend status values from ResearchRunSummary.
 */
export type RunStatus = "pending" | "running" | "completed" | "failed";

/**
 * Props for IdeationQueueRunItem component (ISP-compliant: minimal interface)
 */
export interface IdeationQueueRunItemProps {
  runId: string;
  status: string;
  gpuType: string | null;
  createdAt: string;
}

/**
 * Props for IdeationQueueRunsList component
 */
export interface IdeationQueueRunsListProps {
  conversationId: number;
}

/**
 * Return type for useConversationResearchRuns hook
 * Uses the auto-generated ResearchRunSummary type from ConversationResponse
 */
export interface UseConversationResearchRunsReturn {
  runs: ResearchRunSummary[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

// Re-export the ResearchRunSummary type for convenience
export type { ResearchRunSummary } from "@/types";
```

### Type Derivation Strategy

We derive `ResearchRunSummary` from the auto-generated API types rather than creating a duplicate:

```typescript
// In the hook file, derive the type from ConversationResponse
type ResearchRunSummary = NonNullable<ConversationResponse["research_runs"]>[number];
```

This ensures:
1. Type safety aligned with backend
2. Automatic updates when API schema changes
3. No manual type duplication

---

## 5. Data Flow Diagram

```
                          User Action
                              |
                              v
+------------------------------------------------------------------+
|                     ConversationsPage                             |
|                              |                                    |
|              useDashboard() returns conversations[]               |
|                              |                                    |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                     IdeationQueueList                             |
|                              |                                    |
|              Maps conversations to IdeationQueueCard              |
|                              |                                    |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                     IdeationQueueCard                             |
|                              |                                    |
|   [User clicks expand] --> setIsExpanded(true)                    |
|                              |                                    |
|   [isExpanded = true] --> Render IdeationQueueRunsList            |
|                              |                                    |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                   IdeationQueueRunsList                           |
|                              |                                    |
|   useConversationResearchRuns(conversationId)                     |
|                              |                                    |
|                   +--------------------+                          |
|                   |   React Query      |                          |
|                   +--------------------+                          |
|                              |                                    |
|                   Check cache for                                 |
|                   ["conversation-research-runs", id]              |
|                              |                                    |
|            +--------+--------+--------+                           |
|            |        |                 |                           |
|         [hit]   [miss]            [stale]                         |
|            |        |                 |                           |
|         return   fetch API         fetch in                       |
|         cached   /conversations/id background                     |
|            |        |                 |                           |
|            +--------+-----------------+                           |
|                              |                                    |
|   isLoading? --> Show skeleton                                    |
|   error? --> Show error message                                   |
|   runs.length === 0? --> Show empty state                         |
|   runs.length > 0 --> Map to IdeationQueueRunItem                 |
|                              |                                    |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                   IdeationQueueRunItem                            |
|                              |                                    |
|   [User clicks] --> e.stopPropagation()                           |
|                 --> router.push(`/research/${runId}`)             |
|                              |                                    |
|                     Navigate to Research Detail Page              |
|                              |                                    |
+------------------------------------------------------------------+
```

---

## 6. SOLID Principles Analysis

### S - Single Responsibility Principle

| Component | Single Responsibility |
|-----------|----------------------|
| `IdeationQueueCard` | Displays idea card, manages expand/collapse state |
| `IdeationQueueRunsList` | Orchestrates runs display (loading, empty, list states) |
| `IdeationQueueRunItem` | Displays single run, handles navigation |
| `useConversationResearchRuns` | Fetches and caches research runs data |

Each component/hook has exactly one reason to change:
- Card layout changes -> IdeationQueueCard
- Run item display changes -> IdeationQueueRunItem
- Data fetching/caching changes -> useConversationResearchRuns
- Loading/error UI changes -> IdeationQueueRunsList

### O - Open/Closed Principle

**Status Badge System (Already OCP-Compliant)**:
The existing `getStatusBadge()` in `research-utils.tsx` uses a switch statement. While not perfectly OCP, it's acceptable because:
1. Run statuses are defined by backend enum (unlikely to change)
2. Adding new status requires backend change anyway

**Extensibility Points**:
- `IdeationQueueRunItem` accepts status as string, so new statuses work automatically
- Run display limit (5) is a constant that could be made configurable
- Component props are minimal, making composition easy

### L - Liskov Substitution Principle

**Component Substitutability**:
- `IdeationQueueRunsList` can be replaced with any component accepting `conversationId`
- `IdeationQueueRunItem` can be swapped for alternative run display components
- All components follow React conventions (props in, JSX out)

**Type Safety**:
- Types derived from auto-generated API schema
- No type assertions or overrides that could break substitution

### I - Interface Segregation Principle

**Focused Prop Interfaces**:

```typescript
// IdeationQueueRunItemProps - Only what's needed for display
interface IdeationQueueRunItemProps {
  runId: string;
  status: string;
  gpuType: string | null;
  createdAt: string;
  // NOT included: full ResearchRunSummary with pod_id, cost, etc.
}

// IdeationQueueRunsListProps - Minimal trigger for data fetch
interface IdeationQueueRunsListProps {
  conversationId: number;
  // NOT included: runs data (fetched internally)
}
```

**Why This Matters**:
- Components receive only what they need to render
- Easy to test with minimal mock data
- Changes to unused fields don't affect components

### D - Dependency Inversion Principle

**Abstraction Dependencies**:

```typescript
// Hook depends on abstractions, not concretions
// Instead of: import axios from 'axios';
import { apiFetch } from "@/shared/lib/api-client";

// Components depend on hook interface, not implementation
const { runs, isLoading, error } = useConversationResearchRuns(id);
```

**Injection Points**:
- `apiFetch` is the abstraction over HTTP client
- React Query provides the caching abstraction
- Components don't know how data is fetched

---

## 7. Reusability Implementation

### MUST REUSE (Direct Imports)

```typescript
// In IdeationQueueRunItem.tsx
import { getStatusBadge, truncateRunId } from "@/features/research/utils/research-utils";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { cn } from "@/shared/lib/utils";

// In useConversationResearchRuns.ts
import { apiFetch } from "@/shared/lib/api-client";

// Lucide icons
import { Clock, ChevronDown, ChevronUp, ArrowRight } from "lucide-react";
```

### ADAPT (Patterns to Follow)

**React Query Pattern** (from `useRecentResearch.ts`):
```typescript
// Pattern structure we follow
const { data, isLoading, error, refetch } = useQuery({
  queryKey: ["conversation-research-runs", conversationId],
  queryFn: () => fetchConversationResearchRuns(conversationId),
  staleTime: 30 * 1000,
});
```

**Loading Skeleton Pattern** (inline, not separate file):
```typescript
// Simplified skeleton matching existing patterns
function RunsListSkeleton() {
  return (
    <div className="mt-3 space-y-2 border-t border-slate-800 pt-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="animate-pulse rounded-lg border border-slate-800/50 bg-slate-900/30 px-3 py-2">
          <div className="flex items-center gap-3">
            <div className="h-6 w-16 rounded-full bg-slate-700/50" />
            <div className="h-4 w-24 rounded bg-slate-700/50" />
          </div>
        </div>
      ))}
    </div>
  );
}
```

### DO NOT CREATE (Using Existing)

| Asset | Location | Why Not Create |
|-------|----------|----------------|
| Status badge | `research-utils.tsx` | Exact match for run status styling |
| Run ID truncation | `research-utils.tsx` | Already handles "rp-xxx..." format |
| Relative time | `date-utils.ts` | Already used in IdeationQueueCard |
| API client | `api-client.ts` | Standard fetch wrapper |
| ResearchRunSummary type | `api.gen.ts` | Auto-generated from backend |

---

## 8. Navigation Strategy

### Route Structure

| Action | Route | Component |
|--------|-------|-----------|
| Click idea card body | `/conversations/{id}` | ConversationView (existing) |
| Click research run item | `/research/{runId}` | Research detail page (existing) |

### Click Handler Separation

```typescript
// In IdeationQueueCard
const handleCardClick = () => {
  router.push(`/conversations/${id}`);
};

const handleExpandToggle = (e: React.MouseEvent) => {
  e.stopPropagation(); // Don't trigger card navigation
  setIsExpanded((prev) => !prev);
};

// In IdeationQueueRunItem
const handleRunClick = (e: React.MouseEvent) => {
  e.stopPropagation(); // Don't trigger card navigation
  router.push(`/research/${runId}`);
};
```

### Visual Affordances

```
+------------------------------------------------------------------------+
| Card (entire area clickable -> /conversations/id)                       |
|                                                                         |
|   [Status] Title                                                        |
|   Abstract preview...                                                   |
|                                                                         |
|   Created 2h ago  |  Updated 1h ago  |  [v Expand] <-- separate zone    |
|   --------------------------------------------------------              |
|   | [Running] rp-abc123... | RTX A4000 | 2h ago | [->] | <-- run click  |
|   | [Completed] rp-def456... | RTX A5000 | 1d ago | [->] |               |
+------------------------------------------------------------------------+
```

---

## 9. Error Handling Strategy

### Loading State
- Show 3 skeleton rows matching run item dimensions
- Use `animate-pulse` consistent with other loading states

### Empty State
- Simple text: "No research runs yet"
- Subtle styling: `text-slate-500 text-sm`
- No icon (keeps it lightweight)

### Error State
- Show error message inline
- Provide retry button
- Don't break parent card layout

```typescript
function RunsListError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="mt-3 border-t border-slate-800 pt-3">
      <div className="flex items-center justify-between rounded-lg bg-red-500/10 px-3 py-2 text-sm">
        <span className="text-red-400">{message}</span>
        <button
          onClick={onRetry}
          className="text-xs text-red-300 hover:text-red-200"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
```

---

## 10. Implementation Order

Based on dependencies, implement in this order:

1. **Types** (`ideation-queue.types.ts`)
   - Add RunStatus type alias
   - Add props interfaces for new components

2. **Hook** (`useConversationResearchRuns.ts`)
   - Implement data fetching logic
   - Add React Query integration

3. **Run Item** (`IdeationQueueRunItem.tsx`)
   - Create component with imports from research-utils
   - No internal dependencies on other new files

4. **Runs List** (`IdeationQueueRunsList.tsx`)
   - Depends on hook and RunItem
   - Implements loading/empty/error states

5. **Card Modification** (`IdeationQueueCard.tsx`)
   - Add expand/collapse state
   - Integrate RunsList component
   - Update click handling

6. **Index Exports** (`index.ts`)
   - Export new components and hook

---

## 11. Testing Considerations

### Unit Test Focus Areas

| Component | Test Focus |
|-----------|------------|
| `IdeationQueueRunItem` | Correct badge display, truncation, click handling |
| `IdeationQueueRunsList` | Loading/empty/error state rendering |
| `useConversationResearchRuns` | Query key, error handling, data extraction |
| `IdeationQueueCard` | Expand/collapse toggle, click zone separation |

### Integration Test Focus

1. Expand card -> runs load and display
2. Click run -> navigates to `/research/{runId}`
3. Click card body -> navigates to `/conversations/{id}`
4. Multiple expand/collapse cycles -> data cached

---

## Summary

| Category | Count | Details |
|----------|-------|---------|
| New Files | 3 | Hook + 2 components |
| Modified Files | 3 | Card, types, index |
| Reused Assets | 7 | Status badge, truncateRunId, formatRelativeTime, apiFetch, cn, Lucide icons, ResearchRunSummary type |
| SOLID Compliance | 5/5 | SRP, OCP, LSP, ISP, DIP all addressed |

---

## Approval Request

Please review the architecture above. Reply with:
- **"proceed"** or **"yes"** - Continue to Implementation phase
- **"modify: [your feedback]"** - I'll adjust the architecture
- **"elaborate"** - Provide more details and context for review
- **"stop"** - Pause here (progress saved)

Waiting for your approval before continuing...
