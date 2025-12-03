# Architecture Phase

## Agent
feature-architecture-expert

## Timestamp
2025-12-03 15:30

## Input Received
- Context: `.agent/Tasks/research-history-home/00-context.md`
- Planning: `.agent/Tasks/research-history-home/01-planning.md`
- PRD: `.agent/Tasks/research-history-home/PRD.md`
- Reusable Assets: `.agent/Tasks/research-history-home/01a-reusable-assets.md`

## Key Decisions from Planning
1. **New compact component** rather than reusing `ResearchBoardTable` - the existing component is too feature-rich (shows GPU, metrics, progress bars, artifacts) for a simple home page history list
2. **Standalone hook without context** - `useRecentResearch` follows the pattern of `useManualIdeaImport` for simple data fetching
3. **Relaunch action** links to `/conversations/{conversationId}` to keep scope manageable
4. **Extract utilities** - `formatRelativeTime` and `getStatusBadge` should be extracted for reuse
5. **Feature location** - Components go in `features/research/components/` to extend existing research feature

---

## Reusability (CRITICAL SECTION)

### Assets Being REUSED (Do NOT Recreate)
| Asset | Source Location | Used For |
|-------|-----------------|----------|
| `ResearchRun` type | `@/types/research` | Data type for research run objects |
| `ResearchRunListResponseApi` type | `@/types/research` | API response type |
| `convertApiResearchRunList` | `@/shared/lib/api-adapters` | Converting API response to frontend types |
| `apiFetch` | `@/shared/lib/api-client` | Making authenticated API calls |
| `cn` | `@/shared/lib/utils` | Conditional class name merging |
| `Button` | `@/shared/components/ui/button` | Relaunch button |
| `formatDistanceToNow` | `date-fns` | Base date formatting (already installed) |
| Lucide icons | `lucide-react` | `CheckCircle2`, `Clock`, `Loader2`, `AlertCircle`, `RotateCcw`, `FlaskConical` |

### Assets Being EXTRACTED (Refactor for Reuse)
| From | To | Content |
|------|-----|---------|
| `ResearchBoardTable.tsx` lines 29-36 | `shared/lib/date-utils.ts` | `formatRelativeTime()` function |
| `ResearchBoardTable.tsx` lines 38-69 | `features/research/utils/research-utils.ts` | `getStatusBadge()` function |

### Assets Being CREATED (New)
| Asset | Location | Justification |
|-------|----------|---------------|
| `useRecentResearch` | `features/research/hooks/useRecentResearch.ts` | Feature-specific hook for fetching last 10 runs |
| `ResearchHistoryList` | `features/research/components/ResearchHistoryList.tsx` | Container with section header, orchestrates states |
| `ResearchHistoryCard` | `features/research/components/ResearchHistoryCard.tsx` | Compact card for individual research run |
| `ResearchHistoryEmpty` | `features/research/components/ResearchHistoryEmpty.tsx` | Empty state component |
| `ResearchHistorySkeleton` | `features/research/components/ResearchHistorySkeleton.tsx` | Loading skeleton matching card layout |

### Imports Required
```typescript
// Types
import type { ResearchRun, ResearchRunListResponseApi } from "@/types/research";

// API
import { apiFetch } from "@/shared/lib/api-client";
import { convertApiResearchRunList } from "@/shared/lib/api-adapters";

// Utilities (after extraction)
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { getStatusBadge } from "@/features/research/utils/research-utils";
import { cn } from "@/shared/lib/utils";

// Icons
import { CheckCircle2, Clock, Loader2, AlertCircle, RotateCcw, FlaskConical } from "lucide-react";

// Components
import { Button } from "@/shared/components/ui/button";
```

---

## Reasoning

### Frontend Architecture
- **Pattern**: Feature-based component with dedicated hook
- **Rationale**: Follows existing architecture where features are self-contained. The home page stays thin and imports the feature component (same pattern as `CreateHypothesisForm`).
- **Reference**: `features/input-pipeline/components/CreateHypothesisForm.tsx` for integration pattern

### Data Flow
```
Home Page (page.tsx)
    |
    v
ResearchHistoryList (client component)
    |
    +-- useRecentResearch hook
    |       |
    |       +-- apiFetch('/research-runs/?limit=10')
    |       +-- convertApiResearchRunList()
    |       +-- Returns: { researchRuns, isLoading, error, refetch }
    |
    +-- Conditional rendering:
            |
            +-- isLoading? --> ResearchHistorySkeleton
            +-- error? --> Error message
            +-- researchRuns.length === 0? --> ResearchHistoryEmpty
            +-- researchRuns.length > 0? --> ResearchHistoryCard[] (mapped)
```

### Key Interfaces
```typescript
// Hook return type
interface UseRecentResearchReturn {
  researchRuns: ResearchRun[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

// Component props
interface ResearchHistoryCardProps {
  research: ResearchRun;
}
```

---

## Detailed File Structure

### Files to Extract/Refactor

#### `/frontend/src/shared/lib/date-utils.ts` (NEW)
```typescript
/**
 * Shared date utility functions
 */
import { formatDistanceToNow } from "date-fns";

/**
 * Formats a date string as relative time (e.g., "2 hours ago")
 * @param dateString - ISO date string
 * @returns Formatted relative time string
 */
export function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return dateString;
  }
}
```

#### `/frontend/src/features/research/utils/research-utils.ts` (NEW)
```typescript
/**
 * Research-specific utility functions
 */
import { CheckCircle2, Clock, Loader2, AlertCircle } from "lucide-react";

/**
 * Returns a styled status badge for a research run status
 * @param status - Research run status string
 * @returns React element with styled badge
 */
export function getStatusBadge(status: string) {
  switch (status) {
    case "completed":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1.5 text-xs font-medium text-emerald-400">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Completed
        </span>
      );
    case "running":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-400">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Running
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/15 px-3 py-1.5 text-xs font-medium text-red-400">
          <AlertCircle className="h-3.5 w-3.5" />
          Failed
        </span>
      );
    case "pending":
    default:
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1.5 text-xs font-medium text-amber-400">
          <Clock className="h-3.5 w-3.5" />
          Pending
        </span>
      );
  }
}
```

### Files to Modify

#### `/frontend/src/features/research/components/ResearchBoardTable.tsx` (MODIFY)
- Remove inline `formatRelativeTime` function (lines 29-36)
- Remove inline `getStatusBadge` function (lines 38-69)
- Add imports:
```typescript
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { getStatusBadge } from "../utils/research-utils";
```

#### `/frontend/src/app/(dashboard)/page.tsx` (MODIFY)
- Add `ResearchHistoryList` import
- Add component below the hypothesis form card
```tsx
import { ResearchHistoryList } from "@/features/research/components/ResearchHistoryList";

// ... existing code ...

<div className="relative rounded-[28px] border border-slate-800/70 bg-slate-950/80 p-6 text-left shadow-[0_30px_80px_-50px_rgba(125,211,252,0.45)] backdrop-blur">
  <CreateHypothesisForm />
</div>

{/* NEW: Research History Section */}
<ResearchHistoryList />

<p className="text-xs text-slate-500">
  Runs kick off...
</p>
```

### New Files to Create

#### `/frontend/src/features/research/hooks/useRecentResearch.ts` (NEW)
```typescript
"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/shared/lib/api-client";
import { convertApiResearchRunList } from "@/shared/lib/api-adapters";
import type { ResearchRun, ResearchRunListResponseApi } from "@/types/research";

interface UseRecentResearchReturn {
  researchRuns: ResearchRun[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch the 10 most recent research runs for the current user
 */
export function useRecentResearch(): UseRecentResearchReturn {
  const [researchRuns, setResearchRuns] = useState<ResearchRun[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchResearchRuns = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiFetch<ResearchRunListResponseApi>("/research-runs/?limit=10");
      const converted = convertApiResearchRunList(data);
      setResearchRuns(converted.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch research history");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchResearchRuns();
  }, [fetchResearchRuns]);

  return {
    researchRuns,
    isLoading,
    error,
    refetch: fetchResearchRuns,
  };
}
```

#### `/frontend/src/features/research/components/ResearchHistoryList.tsx` (NEW)
```typescript
"use client";

import { useRecentResearch } from "../hooks/useRecentResearch";
import { ResearchHistoryCard } from "./ResearchHistoryCard";
import { ResearchHistoryEmpty } from "./ResearchHistoryEmpty";
import { ResearchHistorySkeleton } from "./ResearchHistorySkeleton";
import { AlertCircle } from "lucide-react";

/**
 * Container component for research history section on home page
 * Handles loading, empty, error, and data states
 */
export function ResearchHistoryList() {
  const { researchRuns, isLoading, error } = useRecentResearch();

  return (
    <div className="w-full text-left">
      <h2 className="mb-4 text-xl font-semibold text-white">
        Your Recent Research
      </h2>

      <div className="rounded-xl border border-slate-800/70 bg-slate-950/80 p-4">
        {isLoading && <ResearchHistorySkeleton />}

        {error && !isLoading && (
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {!isLoading && !error && researchRuns.length === 0 && (
          <ResearchHistoryEmpty />
        )}

        {!isLoading && !error && researchRuns.length > 0 && (
          <div className="space-y-3">
            {researchRuns.map((research) => (
              <ResearchHistoryCard key={research.runId} research={research} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

#### `/frontend/src/features/research/components/ResearchHistoryCard.tsx` (NEW)
```typescript
"use client";

import Link from "next/link";
import { RotateCcw } from "lucide-react";
import type { ResearchRun } from "@/types/research";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { getStatusBadge } from "../utils/research-utils";

interface ResearchHistoryCardProps {
  research: ResearchRun;
}

/**
 * Compact card displaying a single research run for the home page history
 */
export function ResearchHistoryCard({ research }: ResearchHistoryCardProps) {
  return (
    <div className="group rounded-lg border border-slate-800 bg-slate-900/50 p-4 transition-all hover:border-slate-700 hover:bg-slate-900/80">
      {/* Header: Status Badge + Timestamp */}
      <div className="flex items-center justify-between mb-2">
        {getStatusBadge(research.status)}
        <span className="text-xs text-slate-500">
          {formatRelativeTime(research.createdAt)}
        </span>
      </div>

      {/* Title */}
      <h3 className="font-semibold text-white mb-1 line-clamp-1">
        {research.ideaTitle || "Untitled Research"}
      </h3>

      {/* Hypothesis snippet */}
      {research.ideaHypothesis && (
        <p className="text-sm text-slate-400 line-clamp-2 mb-3">
          {research.ideaHypothesis}
        </p>
      )}

      {/* Action Button */}
      <div className="flex justify-end">
        <Link
          href={`/conversations/${research.conversationId}`}
          className="inline-flex items-center gap-1.5 rounded-lg bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-400 transition-colors hover:bg-sky-500/25"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Relaunch
        </Link>
      </div>
    </div>
  );
}
```

#### `/frontend/src/features/research/components/ResearchHistoryEmpty.tsx` (NEW)
```typescript
"use client";

import { FlaskConical } from "lucide-react";

/**
 * Empty state component shown when user has no research history
 */
export function ResearchHistoryEmpty() {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <FlaskConical className="h-10 w-10 text-slate-600 mb-3" />
      <h3 className="text-base font-medium text-slate-300">
        No research history yet
      </h3>
      <p className="mt-1 text-sm text-slate-500">
        Submit your first hypothesis above to get started
      </p>
    </div>
  );
}
```

#### `/frontend/src/features/research/components/ResearchHistorySkeleton.tsx` (NEW)
```typescript
"use client";

/**
 * Loading skeleton for research history cards
 * Shows 3 placeholder cards while data is loading
 */
export function ResearchHistorySkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="animate-pulse rounded-lg border border-slate-800 bg-slate-900/50 p-4"
        >
          {/* Header skeleton */}
          <div className="flex items-center justify-between mb-2">
            <div className="h-6 w-20 rounded-full bg-slate-700/50" />
            <div className="h-4 w-24 rounded bg-slate-700/50" />
          </div>

          {/* Title skeleton */}
          <div className="h-5 w-3/4 rounded bg-slate-700/50 mb-2" />

          {/* Description skeleton */}
          <div className="space-y-1.5 mb-3">
            <div className="h-4 w-full rounded bg-slate-700/50" />
            <div className="h-4 w-5/6 rounded bg-slate-700/50" />
          </div>

          {/* Button skeleton */}
          <div className="flex justify-end">
            <div className="h-7 w-24 rounded-lg bg-slate-700/50" />
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

## Component Specifications

### ResearchHistoryList
- **Purpose**: Container component for the research history section
- **Props**: None (self-contained with hook)
- **State**: Managed by `useRecentResearch` hook
- **Renders**: Section header, conditional content (skeleton/error/empty/cards)
- **Dependencies**: `useRecentResearch`, `ResearchHistoryCard`, `ResearchHistoryEmpty`, `ResearchHistorySkeleton`

### ResearchHistoryCard
- **Purpose**: Display a single research run in compact format
- **Props**: `{ research: ResearchRun }`
- **Renders**: Status badge, timestamp, title, hypothesis snippet, relaunch link
- **Dependencies**: `formatRelativeTime`, `getStatusBadge`, `lucide-react` icons

### ResearchHistoryEmpty
- **Purpose**: Empty state when user has no research runs
- **Props**: None
- **Renders**: Flask icon, heading, helper text
- **Dependencies**: `lucide-react` FlaskConical icon

### ResearchHistorySkeleton
- **Purpose**: Loading placeholder while fetching data
- **Props**: None
- **Renders**: 3 animated placeholder cards matching card layout
- **Dependencies**: None (pure Tailwind CSS animation)

---

## Hook Specification

### useRecentResearch
- **Purpose**: Fetch the 10 most recent research runs for current user
- **Returns**:
  - `researchRuns: ResearchRun[]` - Array of research runs (max 10)
  - `isLoading: boolean` - True while fetching
  - `error: string | null` - Error message if fetch failed
  - `refetch: () => Promise<void>` - Function to manually refetch
- **API**: `GET /research-runs/?limit=10`
- **Error handling**:
  - Catches API errors and sets error state
  - 401 errors auto-redirect to login (handled by `apiFetch`)
- **Pattern**: Follows `useState` + `useEffect` pattern (consistent with research feature)

---

## Integration Points

### Where component is added
- **File**: `/frontend/src/app/(dashboard)/page.tsx`
- **Position**: Between the hypothesis form card and the footer text
- **Import path**: `@/features/research/components/ResearchHistoryList`

### Data flow
1. Home page renders `ResearchHistoryList`
2. `ResearchHistoryList` calls `useRecentResearch` hook
3. Hook fetches from `/api/research-runs/?limit=10` via `apiFetch`
4. Response converted via `convertApiResearchRunList`
5. Component renders appropriate state (loading/error/empty/data)

---

## Implementation Order

1. **Extract utilities** (prerequisite for other files)
   - Create `shared/lib/date-utils.ts` with `formatRelativeTime`
   - Create `features/research/utils/research-utils.ts` with `getStatusBadge`
   - Update `ResearchBoardTable.tsx` to import from extracted files
   - Verify existing research page still works

2. **Create hook**
   - Create `features/research/hooks/useRecentResearch.ts`
   - Test hook in isolation (can add console.log temporarily)

3. **Create skeleton component**
   - Create `ResearchHistorySkeleton.tsx`
   - Provides immediate visual feedback during development

4. **Create empty state component**
   - Create `ResearchHistoryEmpty.tsx`
   - Simple, no dependencies

5. **Create card component**
   - Create `ResearchHistoryCard.tsx`
   - Depends on extracted utilities

6. **Create list container**
   - Create `ResearchHistoryList.tsx`
   - Combines all components

7. **Integrate into home page**
   - Modify `page.tsx` to include `ResearchHistoryList`

8. **Test all states**
   - Loading state (skeleton)
   - Empty state (no research runs)
   - Data state (1-10 research runs)
   - Error state (network failure)

---

## For Next Phase (Implementation)

Guidance for the executor:
- **Recommended implementation order**: Follow the numbered list above
- **Type dependencies**: No circular dependencies; types come from `@/types/research`
- **Critical considerations**:
  - The extraction step MUST be tested by verifying the research board page (`/research`) still works
  - All new components need `"use client"` directive
  - Use existing card styling patterns from `ResearchBoardTable.tsx`
  - The home page is currently a server component but will remain so; only `ResearchHistoryList` needs to be a client component

---

## Approval Status
- [ ] Pending approval
- [ ] Approved - proceed to Implementation
- [ ] Modified - see feedback below

### Feedback
{User feedback if modifications requested}
