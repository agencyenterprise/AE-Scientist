# Reusable Assets Inventory

## Agent
codebase-analyzer

## Timestamp
2025-12-05 11:30

## Feature Requirements Summary

The Ideation Queue Enhancement feature needs:
- Page header with icon, title ("Ideation Queue"), and counts
- Status badges (no_idea, pending_launch, in_research, completed, failed)
- Filterable list/table of conversations with status filtering
- Hypothesis title and abstract preview display
- Date formatting (relative time for created/updated)
- Empty state component for no results
- Search functionality (already exists)
- Sorting capability

---

## MUST REUSE (Exact Match Found)

These assets already exist and MUST be used instead of creating new ones:

### Utilities

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Class name merging | `cn()` | `/frontend/src/shared/lib/utils.ts` | `import { cn } from "@/shared/lib/utils"` |
| Relative time formatting | `formatRelativeTime()` | `/frontend/src/shared/lib/date-utils.ts` | `import { formatRelativeTime } from "@/shared/lib/date-utils"` |
| Date-time formatting | `formatDateTime()` | `/frontend/src/shared/lib/date-utils.ts` | `import { formatDateTime } from "@/shared/lib/date-utils"` |
| Full timestamp formatting | `formatLaunchedTimestamp()` | `/frontend/src/shared/lib/date-utils.ts` | `import { formatLaunchedTimestamp } from "@/shared/lib/date-utils"` |
| Status badge rendering | `getStatusBadge()` | `/frontend/src/features/research/utils/research-utils.tsx` | `import { getStatusBadge } from "@/features/research/utils/research-utils"` |
| Log level colors | `getLogLevelColor()` | `/frontend/src/features/research/utils/research-utils.tsx` | `import { getLogLevelColor } from "@/features/research/utils/research-utils"` |
| ID truncation | `truncateRunId()` | `/frontend/src/features/research/utils/research-utils.tsx` | `import { truncateRunId } from "@/features/research/utils/research-utils"` |

### Hooks

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Search/filter state | `useConversationsFilter()` | `/frontend/src/features/conversation/hooks/useConversationsFilter.ts` | `import { useConversationsFilter } from "@/features/conversation/hooks/useConversationsFilter"` |
| Conversations data | `useDashboard()` | `/frontend/src/features/dashboard/contexts/DashboardContext.tsx` | `import { useDashboard } from "@/features/dashboard/contexts/DashboardContext"` |

### Types

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Conversation type | `Conversation` | `/frontend/src/shared/lib/api-adapters.ts` | `import type { Conversation } from "@/shared/lib/api-adapters"` |
| Sort types | `SortKey`, `SortDir` | `/frontend/src/features/dashboard/contexts/DashboardContext.tsx` | `import type { SortKey, SortDir } from "@/features/dashboard/contexts/DashboardContext"` |
| Research run status | `ResearchRunStatus` | `/frontend/src/types/research.ts` | `import type { ResearchRunStatus } from "@/types/research"` |

### UI Components

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Button component | `Button` | `/frontend/src/shared/components/ui/button.tsx` | `import { Button } from "@/shared/components/ui/button"` |
| Tooltip component | `Tooltip`, `TooltipTrigger`, `TooltipContent` | `/frontend/src/shared/components/ui/tooltip.tsx` | `import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/components/ui/tooltip"` |
| Progress bar | `ProgressBar` | `/frontend/src/shared/components/ui/progress-bar.tsx` | `import { ProgressBar } from "@/shared/components/ui/progress-bar"` |

### External Libraries (Already Installed)

| Need | Package | Usage Example |
|------|---------|---------------|
| Date formatting | `date-fns` | `import { formatDistanceToNow, format } from "date-fns"` |
| Icons | `lucide-react` | `import { Lightbulb, Clock, CheckCircle2, AlertCircle, Loader2 } from "lucide-react"` |
| Class variance | `class-variance-authority` | `import { cva, type VariantProps } from "class-variance-authority"` |
| Class merging | `clsx` + `tailwind-merge` | Already wrapped in `cn()` utility |

---

## CONSIDER REUSING (Similar Found)

These assets are similar and can be adapted or referenced for patterns:

### Components to Reference

| Need | Similar Asset | Location | Notes |
|------|---------------|----------|-------|
| Page header with icon | `ConversationsBoardHeader` | `/frontend/src/features/conversation/components/ConversationsBoardHeader.tsx` | Adapt: change icon to Lightbulb, title to "Ideation Queue", add status filter buttons |
| Page header with filters | `ResearchBoardHeader` | `/frontend/src/features/research/components/ResearchBoardHeader.tsx` | **Better reference** - has search + status filter dropdown pattern |
| Table with actions | `ConversationsBoardTable` | `/frontend/src/features/conversation/components/ConversationsBoardTable.tsx` | Adapt: add status badge column, abstract preview, better empty state |
| Card with status | `ResearchHistoryCard` | `/frontend/src/features/research/components/ResearchHistoryCard.tsx` | Reference for inline status badges with colors |
| Card structure | `ResearchBoardCard` | `/frontend/src/features/research/components/research-board-card.tsx` | Reference for header/body/footer card structure |
| Empty state | `ResearchBoardEmpty` | `/frontend/src/features/research/components/research-board-empty.tsx` | Adapt: change icon and message text |
| Empty state (alt) | `ResearchHistoryEmpty` | `/frontend/src/features/research/components/ResearchHistoryEmpty.tsx` | Similar pattern for empty state |
| Filter buttons | `ResearchLogsList` | `/frontend/src/features/research/components/run-detail/research-logs-list.tsx` | **Copy this pattern** - has LOG_FILTER_CONFIG with active states |

### Patterns to Copy

| Pattern | Source | How to Apply |
|---------|--------|--------------|
| Filter button config | `LOG_FILTER_CONFIG` in research-logs-list.tsx | Create `STATUS_FILTER_CONFIG` with IdeaStatus options and color classes |
| Status badge sizes | `STATUS_BADGE_SIZES` in research-utils.tsx | Can reuse directly or adapt for idea badges |
| Stage badge config | `DEFAULT_STAGE_CONFIGS` in research-utils.tsx | Reference for Open/Closed compliance color patterns |
| Card hover effect | research-board-card.tsx | `hover:border-slate-700 hover:bg-slate-900/80` transition pattern |
| Text truncation | ResearchHistoryCard.tsx | `line-clamp-2` for title, `line-clamp-4` for hypothesis preview |

---

## CREATE NEW (Nothing Found)

These need to be created as no existing solution was found:

### Types to Create

| Need | Suggested Location | Notes |
|------|-------------------|-------|
| `IdeaStatus` type | `/frontend/src/features/conversation/types/ideation-queue.types.ts` | `"no_idea" \| "pending_launch" \| "in_research" \| "completed" \| "failed"` |
| `IdeaStatusConfig` interface | `/frontend/src/features/conversation/types/ideation-queue.types.ts` | `{ label: string; className: string; icon: ComponentType }` |
| `StatusFilterOption` type | `/frontend/src/features/conversation/types/ideation-queue.types.ts` | `"all" \| IdeaStatus` |

### Utilities to Create

| Need | Suggested Location | Notes |
|------|-------------------|-------|
| `deriveIdeaStatus()` | `/frontend/src/features/conversation/utils/ideation-queue-utils.ts` | Derives status from Conversation fields (MVP: based on ideaTitle presence) |
| `getIdeaStatusBadge()` | `/frontend/src/features/conversation/utils/ideation-queue-utils.ts` | Returns styled badge JSX for idea status (adapt from getStatusBadge) |
| `IDEA_STATUS_CONFIG` | `/frontend/src/features/conversation/utils/ideation-queue-utils.ts` | Configuration map for status badge styling |
| `STATUS_FILTER_OPTIONS` | `/frontend/src/features/conversation/utils/ideation-queue-utils.ts` | Array of filter options: `["all", "no_idea", "pending_launch", ...]` |

### Components to Create

| Need | Suggested Location | Notes |
|------|-------------------|-------|
| `IdeationQueueHeader` | `/frontend/src/features/conversation/components/IdeationQueueHeader.tsx` | Combine ConversationsBoardHeader + ResearchBoardHeader patterns |
| `IdeationQueueRow` | `/frontend/src/features/conversation/components/IdeationQueueRow.tsx` | Enhanced row with status badge, title, abstract preview, dates |
| `IdeationQueueTable` | `/frontend/src/features/conversation/components/IdeationQueueTable.tsx` | Table wrapper using IdeationQueueRow |
| `IdeationQueueFilters` | `/frontend/src/features/conversation/components/IdeationQueueFilters.tsx` | Status filter buttons (follow LOG_FILTER_CONFIG pattern) |
| `IdeationQueueEmpty` | `/frontend/src/features/conversation/components/IdeationQueueEmpty.tsx` | Empty state (adapt ResearchBoardEmpty with Lightbulb icon) |

### Hooks to Create/Modify

| Need | Suggested Location | Notes |
|------|-------------------|-------|
| Extended filter hook | Modify `/frontend/src/features/conversation/hooks/useConversationsFilter.ts` | Add `statusFilter` state and filtered results by status |
| `useIdeationQueueSort` | `/frontend/src/features/conversation/hooks/useIdeationQueueSort.ts` | Sorting logic (newest, oldest, title, status) - OR extend existing SortKey in DashboardContext |

---

## CONSIDER EXTRACTING TO SHARED

These feature-specific assets could be generalized for reuse:

| Current Location | Asset | Suggested New Location | Why |
|------------------|-------|------------------------|-----|
| `features/research/utils/research-utils.tsx` | `getStatusBadge()` | `shared/components/StatusBadge.tsx` | Generic status badge component usable across features |
| `features/conversation/components/ConversationsBoardTable.tsx` | `truncateId()` | `shared/lib/string-utils.ts` | Generic truncation utility |
| `features/research/utils/research-utils.tsx` | `truncateRunId()` | `shared/lib/string-utils.ts` | Same pattern, should be consolidated |

---

## Patterns Already Established

Document existing patterns the feature should follow:

### State Management Pattern
- **Data Source**: `useDashboard()` provides `conversations` array from DashboardContext
- **Local Filter State**: `useState` for filter values within components
- **Derived State**: `useMemo` for filtered/sorted results (see `useConversationsFilter`)

### Component Structure Pattern
```
features/conversation/
├── components/
│   ├── IdeationQueue*.tsx    # New components
│   └── Conversations*.tsx    # Keep existing (deprecated but functional)
├── hooks/
│   └── useConversationsFilter.ts  # Extend for status
├── utils/
│   └── ideation-queue-utils.ts    # New utilities
├── types/
│   └── ideation-queue.types.ts    # New types
└── index.ts                       # Export all
```

### Filter UI Pattern (from research-logs-list.tsx)
```typescript
// Configuration-driven filter buttons
const FILTER_CONFIG: Record<FilterType, { label: string; activeClass: string }> = {
  all: { label: "all", activeClass: "bg-slate-500/15 text-slate-300" },
  // ...
};

// Button rendering with cn() for conditional classes
<button
  className={cn(
    "rounded-md px-3 py-1 text-xs font-medium transition-colors",
    activeFilter === option
      ? FILTER_CONFIG[option].activeClass
      : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
  )}
>
```

### Status Badge Color Pattern (explicit Tailwind classes for v4)
```typescript
// From research-utils.tsx - explicit color classes, NOT computed
{
  completed: "bg-emerald-500/15 text-emerald-400",
  running: "bg-sky-500/15 text-sky-400",
  failed: "bg-red-500/15 text-red-400",
  pending: "bg-amber-500/15 text-amber-400",
}
```

### Empty State Pattern
```tsx
// From ResearchBoardEmpty
<div className="flex h-64 items-center justify-center">
  <div className="text-center">
    <Icon className="mx-auto mb-3 h-10 w-10 text-slate-600" />
    <h3 className="text-lg font-medium text-slate-300">Title</h3>
    <p className="mt-1 text-sm text-slate-500">Description</p>
  </div>
</div>
```

### Text Truncation Pattern
```tsx
// Title: 2 lines max
<p className="line-clamp-2 text-sm font-semibold text-slate-100">
  {title}
</p>

// Abstract: 4 lines max  
<p className="line-clamp-4 text-xs text-slate-300">
  {abstract}
</p>
```

---

## Import Reference

Ready-to-use import statements for all reusable assets:

```typescript
// Utilities
import { cn } from "@/shared/lib/utils";
import { formatRelativeTime, formatDateTime } from "@/shared/lib/date-utils";
import { getStatusBadge, truncateRunId } from "@/features/research/utils/research-utils";

// Hooks
import { useConversationsFilter } from "@/features/conversation/hooks/useConversationsFilter";
import { useDashboard } from "@/features/dashboard/contexts/DashboardContext";

// Types
import type { Conversation } from "@/shared/lib/api-adapters";
import type { SortKey, SortDir } from "@/features/dashboard/contexts/DashboardContext";

// Components
import { Button } from "@/shared/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/components/ui/tooltip";
import { ProgressBar } from "@/shared/components/ui/progress-bar";

// Icons (lucide-react)
import { 
  Lightbulb,      // Ideation Queue icon
  Clock,          // Pending status
  Loader2,        // Running status (with animate-spin)
  CheckCircle2,   // Completed status
  AlertCircle,    // Failed status
  FileQuestion,   // No idea status
  Search,         // Search input
  Eye,            // View action
  ArrowRight,     // View button arrow
} from "lucide-react";
```

---

## For Architect

Key reusability requirements:

1. **DO NOT** create new:
   - Date formatting utilities (use `date-utils.ts`)
   - Class merging utilities (use `cn()`)
   - Base status badge logic (adapt `getStatusBadge()` pattern)
   - Empty state from scratch (adapt existing pattern)

2. **REUSE** from:
   - `@/shared/lib/utils` - cn()
   - `@/shared/lib/date-utils` - all date formatting
   - `@/features/research/utils/research-utils` - badge patterns
   - `@/features/conversation/hooks/useConversationsFilter` - extend for status

3. **FOLLOW** patterns from:
   - `ResearchBoardHeader` - header with filter controls
   - `ResearchLogsList` - filter button configuration
   - `ResearchHistoryCard` - card structure with status
   - `ResearchBoardEmpty` - empty state structure

4. **Note**: The `Conversation` type already includes `ideaTitle` and `ideaAbstract` fields that can be used for MVP status derivation.

---

## For Executor

Before implementing ANY utility/hook/component:

1. **Check this inventory first** for existing solutions
2. **Search the codebase** using grep if asset not listed:
   ```bash
   grep -rn "export function|export const" frontend/src/shared/
   grep -rn "your-function-name" frontend/src/
   ```
3. **Only create new** if confirmed nothing exists
4. **Follow established patterns** documented above

### Quick Checklist
- [ ] Status badge: Adapt from `getStatusBadge()` pattern
- [ ] Filter buttons: Copy `LOG_FILTER_CONFIG` pattern
- [ ] Empty state: Adapt from `ResearchBoardEmpty`
- [ ] Header: Combine `ConversationsBoardHeader` + `ResearchBoardHeader`
- [ ] Date formatting: Use `formatRelativeTime()` from date-utils
- [ ] Class merging: Use `cn()` utility
- [ ] Text truncation: Use `line-clamp-*` classes

