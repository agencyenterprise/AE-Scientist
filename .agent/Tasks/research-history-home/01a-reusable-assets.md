# Reusable Assets Inventory

## Agent
codebase-analyzer

## Timestamp
2025-12-03 14:30

## Feature Requirements Summary
The Research History feature needs:
- A list component showing the 10 most recent research runs
- Individual card components for each run displaying: title, status badge, relative timestamp, hypothesis snippet
- Status badge with color-coded states (pending, running, completed, failed)
- Relative time formatting (e.g., "2 hours ago")
- Empty state when user has no history
- Loading skeleton while fetching
- "Relaunch" action button linking to conversation page
- API hook to fetch data from `GET /api/research-runs/?limit=10`

---

## MUST REUSE (Exact Match Found)

These assets already exist and MUST be used instead of creating new ones:

### Frontend - Types & API

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Research run type | `ResearchRun` | `/frontend/src/types/research.ts` | `import type { ResearchRun, ResearchRunListResponseApi } from "@/types/research"` |
| API response converter | `convertApiResearchRunList` | `/frontend/src/shared/lib/api-adapters.ts` | `import { convertApiResearchRunList } from "@/shared/lib/api-adapters"` |
| Single run converter | `convertApiResearchRun` | `/frontend/src/shared/lib/api-adapters.ts` | `import { convertApiResearchRun } from "@/shared/lib/api-adapters"` |
| API client | `apiFetch` | `/frontend/src/shared/lib/api-client.ts` | `import { apiFetch } from "@/shared/lib/api-client"` |
| Class name utility | `cn` | `/frontend/src/shared/lib/utils.ts` | `import { cn } from "@/shared/lib/utils"` |

### Frontend - UI Components

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Button component | `Button` | `/frontend/src/shared/components/ui/button.tsx` | `import { Button } from "@/shared/components/ui/button"` |

### Frontend - Dependencies (already installed)

| Need | Package | Usage Example |
|------|---------|---------------|
| Date formatting | `date-fns` | `import { formatDistanceToNow } from "date-fns"` |
| Icons | `lucide-react` | `import { CheckCircle2, Clock, Loader2, AlertCircle } from "lucide-react"` |

---

## CONSIDER REUSING (Similar Found - May Need Adaptation)

These assets are similar to what we need but require extraction or adaptation:

### Frontend

| Need | Similar Asset | Location | Notes |
|------|---------------|----------|-------|
| Status badge rendering | `getStatusBadge()` function | `/frontend/src/features/research/components/ResearchBoardTable.tsx` (lines 38-69) | **EXTRACT** - Identical logic needed. Extract to shared utility. |
| Relative time formatting | `formatRelativeTime()` function | `/frontend/src/features/research/components/ResearchBoardTable.tsx` (lines 29-36) | **EXTRACT** - Same function exists in 3 places. Extract to shared utility. |
| Empty state pattern | Inline JSX | `/frontend/src/features/research/components/ResearchBoardTable.tsx` (lines 135-145) | Reference for consistent empty state styling |
| Empty state pattern | Inline JSX | `/frontend/src/features/conversation/components/ConversationsBoardTable.tsx` (lines 40-48) | Reference pattern |
| Loading spinner | Inline JSX | `/frontend/src/features/search/components/SearchResults.tsx` (lines 264-268) | Reference for loading state pattern |
| Card styling | `ConversationCard` | `/frontend/src/features/conversation/components/ConversationCard.tsx` | Reference for card border/hover patterns |
| Skeleton component | `ProjectDraftSkeleton` | `/frontend/src/features/project-draft/components/ProjectDraftSkeleton.tsx` | Reference for skeleton animation pattern |

---

## CREATE NEW (Nothing Suitable Exists)

These need to be created as no existing solution was found:

| Asset | Suggested Location | Notes |
|-------|-------------------|-------|
| `useRecentResearch` hook | `/frontend/src/features/research/hooks/useRecentResearch.ts` | Simple hook to fetch last 10 runs using `apiFetch` and `convertApiResearchRunList` |
| `ResearchHistoryList` | `/frontend/src/features/research/components/ResearchHistoryList.tsx` | Container component with section header, loading, empty states |
| `ResearchHistoryCard` | `/frontend/src/features/research/components/ResearchHistoryCard.tsx` | Compact card for individual research run |
| `ResearchHistoryEmpty` | `/frontend/src/features/research/components/ResearchHistoryEmpty.tsx` | Empty state with icon and message |
| `ResearchHistorySkeleton` | `/frontend/src/features/research/components/ResearchHistorySkeleton.tsx` | Loading skeleton matching card layout |

---

## EXTRACTION CANDIDATES (Refactor for Reuse)

These functions are duplicated across the codebase and should be extracted to shared utilities:

| Code | Current Locations | Extract To | Why |
|------|-------------------|------------|-----|
| `formatRelativeTime()` | `ResearchBoardTable.tsx`, `ConversationsBoardTable.tsx`, `research/[runId]/page.tsx` | `/frontend/src/shared/lib/date-utils.ts` | Identical function duplicated in 3+ places |
| `getStatusBadge()` | `ResearchBoardTable.tsx`, `research/[runId]/page.tsx` | `/frontend/src/features/research/utils/research-utils.ts` | Research-specific but used in multiple places |
| `truncateRunId()` | `ResearchBoardTable.tsx` | Keep in place or move to research utils | Only used once currently |

---

## Patterns Already Established

### State Management Pattern
- **Simple data fetching**: Use `useState` + `useEffect` with `apiFetch` (no React Query in research feature)
- **Context for shared state**: `ResearchContext` provides research runs list with pagination for the research board
- For a simple "last 10" fetch, a standalone hook without context is appropriate (matches `useManualIdeaImport` pattern)

### API Client Pattern
```typescript
const data = await apiFetch<ResearchRunListResponseApi>('/research-runs/?limit=10');
const converted = convertApiResearchRunList(data);
```

### Component Structure Pattern
- Feature components live in `features/{feature}/components/`
- Hooks live in `features/{feature}/hooks/`
- Home page imports feature components directly (see `CreateHypothesisForm` usage)

### Error Handling Pattern
- API errors throw `ApiError` with status code
- Components show error state inline
- 401 errors auto-redirect to login (handled by `apiFetch`)

### Card Styling Pattern
From `ResearchBoardTable.tsx`:
```typescript
className="group rounded-xl border border-slate-800 bg-slate-900/50 transition-all hover:border-slate-700 hover:bg-slate-900/80"
```

### Status Badge Pattern (from `ResearchBoardTable.tsx`)
```typescript
// Completed
"inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1.5 text-xs font-medium text-emerald-400"
// Running (with animated spinner)
"inline-flex items-center gap-1.5 rounded-full bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-400"
// Failed
"inline-flex items-center gap-1.5 rounded-full bg-red-500/15 px-3 py-1.5 text-xs font-medium text-red-400"
// Pending
"inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1.5 text-xs font-medium text-amber-400"
```

### Empty State Pattern
```typescript
<div className="flex h-64 items-center justify-center">
  <div className="text-center">
    <h3 className="text-lg font-medium text-slate-300">No research runs found</h3>
    <p className="mt-1 text-sm text-slate-500">Start a research pipeline run from a conversation.</p>
  </div>
</div>
```

### Skeleton Animation Pattern
```typescript
<div className="animate-pulse space-y-2">
  <div className="h-3 bg-primary/30 rounded w-full"></div>
  <div className="h-3 bg-primary/30 rounded w-5/6"></div>
</div>
```

---

## For Architect

Key reusability requirements:
1. **DO NOT** recreate:
   - `ResearchRun` type - import from `@/types/research`
   - `convertApiResearchRunList` - import from `@/shared/lib/api-adapters`
   - `apiFetch` - import from `@/shared/lib/api-client`
   - `cn` utility - import from `@/shared/lib/utils`
   - `Button` component - import from `@/shared/components/ui/button`
   - `date-fns` or icon libraries - already installed

2. **EXTRACT** before implementing:
   - `formatRelativeTime()` to shared date utils (currently duplicated 3x)
   - `getStatusBadge()` to research utils (used in 2+ places)

3. **FOLLOW** patterns from:
   - `ResearchBoardTable.tsx` - card styling, status badges, empty state
   - `CreateHypothesisForm.tsx` - how to integrate feature component into home page
   - `ProjectDraftSkeleton.tsx` - skeleton animation pattern

4. **REFERENCE** for styling:
   - Home page container: `max-w-3xl` width
   - Card container from home page: `rounded-[28px] border border-slate-800/70 bg-slate-950/80`

---

## For Executor

Before implementing ANY utility/hook/component:
1. Check this inventory first
2. Search the codebase if not listed here
3. Only create new if confirmed nothing exists

### Required Imports Summary

```typescript
// Types
import type { ResearchRun, ResearchRunListResponseApi } from "@/types/research";

// API
import { apiFetch } from "@/shared/lib/api-client";
import { convertApiResearchRunList } from "@/shared/lib/api-adapters";

// Utilities
import { cn } from "@/shared/lib/utils";
import { formatDistanceToNow } from "date-fns";

// Icons (as needed)
import { CheckCircle2, Clock, Loader2, AlertCircle, RotateCcw, FlaskConical } from "lucide-react";

// Components
import { Button } from "@/shared/components/ui/button";
```

---

## Code Snippets for Reference

### Status Badge Function (to extract)
From `/frontend/src/features/research/components/ResearchBoardTable.tsx`:
```typescript
function getStatusBadge(status: string) {
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

### Relative Time Function (to extract)
From `/frontend/src/features/research/components/ResearchBoardTable.tsx`:
```typescript
function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return dateString;
  }
}
```
