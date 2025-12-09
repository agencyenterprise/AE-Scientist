# Architecture Phase

## Architecture Updates

### Revision 1: Table to Card Layout
**Date**: 2025-12-05
**Reason**: User feedback - cards are more flexible for adding information in the future
**Changes**:
- Replaced `IdeationQueueTable.tsx` with `IdeationQueueList.tsx` (card list container)
- Replaced `IdeationQueueRow.tsx` with `IdeationQueueCard.tsx` (individual card component)
- Updated component hierarchy to use responsive grid layout
- Updated data flow diagram and implementation order

---

## Agent
feature-architecture-expert

## Timestamp
2025-12-05 12:00 (Initial)
2025-12-05 14:30 (Revision 1: Table to Card)

## Input Received
- Context: `.agent/Tasks/ideation-queue-enhancement/00-context.md`
- Planning: `.agent/Tasks/ideation-queue-enhancement/01-planning.md`
- PRD: `.agent/Tasks/ideation-queue-enhancement/PRD.md`
- Reusable Assets: `.agent/Tasks/ideation-queue-enhancement/01a-reusable-assets.md`

## Key Decisions from Planning

1. **Route path**: Keep `/conversations` - avoid breaking existing links
2. **Feature location**: Enhance `features/conversation/` - reuse existing data flow
3. **Status source**: Derive from existing fields for MVP (no backend changes)
4. **Component strategy**: Create new components, keep old ones (deprecated but functional)
5. **Badge styling**: Adapt from `research-utils.tsx` pattern
6. **Filter pattern**: Use `LOG_FILTER_CONFIG` style from `research-logs-list.tsx`

## Card Layout Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Layout method** | CSS Grid | More control over responsive columns; easier gap management |
| **Card wrapper** | Custom card (not PageCard) | PageCard is for full-page containers; need individual item cards |
| **Card height** | Auto-height | Content varies (some have abstracts, some don't); auto-height is more natural |
| **Responsive columns** | 1 col (mobile), 2 cols (md), 3 cols (lg) | Balances information density with readability |
| **Card clickability** | Entire card is clickable | Better UX; follows ResearchHistoryCard pattern |
| **Card reference** | `ResearchHistoryCard.tsx` | Similar content structure (title, description, dates, status) |

---

## Reusability (CRITICAL SECTION)

### Assets Being REUSED (Do NOT Recreate)

| Asset | Source Location | Used For |
|-------|-----------------|----------|
| `cn()` | `@/shared/lib/utils` | Conditional class merging |
| `formatRelativeTime()` | `@/shared/lib/date-utils` | Relative time display |
| `useDashboard()` | `@/features/dashboard/contexts/DashboardContext` | Source of `conversations` data |
| `useConversationsFilter()` | `@/features/conversation/hooks/useConversationsFilter` | Base filter logic (to extend) |
| `Conversation` type | `@/shared/lib/api-adapters` | Conversation data model |
| `Button` | `@/shared/components/ui/button` | Action buttons |
| `Tooltip` components | `@/shared/components/ui/tooltip` | Tooltip for truncated text |
| Lucide icons | `lucide-react` | All icons |

### Assets Being CREATED (New)

| Asset | Location | Justification |
|-------|----------|---------------|
| `IdeaStatus` type | `types/ideation-queue.types.ts` | Feature-specific status enum |
| `IdeaStatusConfig` interface | `types/ideation-queue.types.ts` | Type-safe badge configuration |
| `IDEA_STATUS_CONFIG` | `utils/ideation-queue-utils.ts` | OCP-compliant status styling |
| `deriveIdeaStatus()` | `utils/ideation-queue-utils.ts` | Status derivation logic |
| `getIdeaStatusBadge()` | `utils/ideation-queue-utils.ts` | Status badge renderer |
| `IdeationQueueHeader` | `components/IdeationQueueHeader.tsx` | New header with filters |
| `IdeationQueueList` | `components/IdeationQueueList.tsx` | **Card grid container** (was Table) |
| `IdeationQueueCard` | `components/IdeationQueueCard.tsx` | **Individual card component** (was Row) |
| `IdeationQueueFilters` | `components/IdeationQueueFilters.tsx` | Status filter buttons |
| `IdeationQueueEmpty` | `components/IdeationQueueEmpty.tsx` | Empty state component |

### Imports Required

```typescript
// From shared utilities
import { cn } from "@/shared/lib/utils";
import { formatRelativeTime } from "@/shared/lib/date-utils";

// From shared UI components
import { Button } from "@/shared/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@/shared/components/ui/tooltip";

// From existing features
import { useDashboard } from "@/features/dashboard/contexts/DashboardContext";
import { useConversationsFilter } from "@/features/conversation/hooks/useConversationsFilter";

// From types
import type { Conversation } from "@/shared/lib/api-adapters";

// Icons (lucide-react)
import {
  Lightbulb,      // Ideation Queue icon
  Clock,          // Pending status
  Loader2,        // Running status
  CheckCircle2,   // Completed status
  AlertCircle,    // Failed status
  FileQuestion,   // No idea status
  Search,         // Search input
  Eye,            // View action
  ArrowRight,     // View button arrow
} from "lucide-react";
```

---

## SOLID Analysis (CRITICAL SECTION)

### Principles Applied in This Design

| Principle | How Applied |
|-----------|-------------|
| **SRP** | Each file has ONE responsibility: types define contracts, utils handle logic, components handle rendering, hooks handle state |
| **OCP** | `IDEA_STATUS_CONFIG` and `STATUS_FILTER_CONFIG` allow adding new statuses without modifying existing components. **Card layout is more extensible** - adding new fields only requires updating card content, not restructuring columns |
| **LSP** | All filter hooks return the same interface; components accept `Conversation[]` without caring about filtering implementation |
| **ISP** | Props interfaces are focused: `IdeationQueueCardProps` only has what a card needs, not everything in `Conversation` |
| **DIP** | Components depend on abstractions (`IdeaStatus` type) not concrete implementations; status derivation is injected via config |

### Why Cards Better Support OCP (Open/Closed Principle)

**Table Layout (Previous)**:
- Adding a new column requires modifying header + row component
- Column width adjustments affect all other columns
- Mobile responsiveness requires hiding columns (information loss)

**Card Layout (Current)**:
- Adding new information = add new element in card body
- No impact on existing elements
- All information remains visible on mobile (card just gets taller)
- Future additions (tags, progress bars, action buttons) fit naturally

### SOLID Violations Found in Existing Code

| File | Violation | Impact | Refactoring Needed |
|------|-----------|--------|-------------------|
| `ConversationsBoardTable.tsx` | **SRP** - Contains its own `truncateId()` and `formatRelativeTime()` functions | Duplicated logic, harder to maintain | **No** - Will use shared utilities in new components |
| `ConversationsBoardTable.tsx` | **OCP** - Empty state is hardcoded inline | Cannot customize without modifying | **No** - New design extracts to separate component |
| `useConversationsFilter.ts` | **OCP** - Only supports search, cannot extend for status filter | Must modify to add status filtering | **Yes - during feature** - Will extend hook |

### Refactoring Plan

**Priority: Medium** (Do during feature work)
- [x] Extract status filtering into `useConversationsFilter` extension
- [x] Use shared `formatRelativeTime()` instead of local function
- [x] Create reusable empty state component

**Priority: Low** (Technical debt for later)
- [ ] Consider extracting `truncateId()` to `@/shared/lib/string-utils.ts`
- [ ] Consolidate `truncateId()` with `truncateRunId()` from research-utils

### Architecture Decisions for SOLID Compliance

1. **Component Separation (SRP)**
   - Data fetching: `useDashboard()` context (existing)
   - Filter state: `useConversationsFilter()` hook (extended)
   - Status derivation: `utils/ideation-queue-utils.ts`
   - Rendering: `components/*.tsx`

2. **Extensibility Points (OCP)**
   - Status configuration via `IDEA_STATUS_CONFIG` constant
   - Filter configuration via `STATUS_FILTER_CONFIG` constant
   - **Card layout enables adding new sections without breaking existing layout**
   - New statuses can be added by updating config, not components

3. **Dependency Injection (DIP)**
   - Components receive `conversations: Conversation[]` - don't fetch themselves
   - Status derivation accepts config parameter for customization
   - Filter state passed as props, not accessed directly

---

## Reasoning

### Frontend Architecture

- **Pattern**: Enhanced feature components with utility extraction
- **Rationale**: Follows existing project conventions while improving code organization
- **SOLID alignment**: SRP (separated concerns), OCP (config-driven + card layout), DIP (prop injection)
- **Reference**: `features/research/components/ResearchHistoryCard.tsx` for card pattern

### Card Layout Rationale

Cards were chosen over tables because:

1. **Future Extensibility**: Cards can easily accommodate new fields (tags, progress indicators, action buttons) without restructuring
2. **Better Mobile UX**: Cards stack vertically on mobile, showing all information; tables require horizontal scrolling or column hiding
3. **Visual Hierarchy**: Cards allow for more flexible information grouping (badge + title on top, abstract in middle, dates at bottom)
4. **Consistent Pattern**: Matches `ResearchHistoryCard` used elsewhere in the application
5. **User Feedback**: Direct request for cards to enable adding more information in the future

### Data Flow

```
useDashboard()
      |
      v
[conversations: Conversation[]]
      |
      v
useConversationsFilter() -- extended with statusFilter
      |
      v
[filteredConversations, searchTerm, statusFilter]
      |
      +---> IdeationQueueHeader (counts, search input, status filter buttons)
      |
      +---> IdeationQueueList
                  |
                  v
            [CSS Grid: responsive columns]
                  |
                  v
            [foreach conversation]
                  |
                  v
            IdeationQueueCard (deriveIdeaStatus -> getIdeaStatusBadge)
                  |
                  v
            [render: badge, title, abstract, dates, clickable link]
```

### Key Interfaces

All interactions happen through well-defined TypeScript interfaces, enabling DIP compliance.

---

## File Structure

### Files to CREATE

```
frontend/src/features/conversation/
|
+-- types/
|   +-- ideation-queue.types.ts        # NEW: Type definitions
|
+-- utils/
|   +-- ideation-queue-utils.ts        # NEW: Status derivation, badge config
|
+-- components/
|   +-- IdeationQueueHeader.tsx        # NEW: Header with filters
|   +-- IdeationQueueList.tsx          # NEW: Card grid container (was Table)
|   +-- IdeationQueueCard.tsx          # NEW: Individual card (was Row)
|   +-- IdeationQueueFilters.tsx       # NEW: Filter button group
|   +-- IdeationQueueEmpty.tsx         # NEW: Empty state
```

### Files to MODIFY

```
frontend/src/features/conversation/
|
+-- hooks/
|   +-- useConversationsFilter.ts      # MODIFY: Add statusFilter state
|
+-- index.ts                           # MODIFY: Add new exports

frontend/src/app/(dashboard)/conversations/
|
+-- page.tsx                           # MODIFY: Use new components
```

### Complete Directory Tree After Implementation

```
frontend/src/features/conversation/
|-- components/
|   |-- ConversationCard.tsx           # KEEP (existing)
|   |-- ConversationHeader.tsx         # KEEP (existing)
|   |-- ConversationsGrid.tsx          # KEEP (existing)
|   |-- ConversationsTable.tsx         # KEEP (existing)
|   |-- ConversationView.tsx           # KEEP (existing)
|   |-- ConversationsBoardHeader.tsx   # KEEP (deprecated)
|   |-- ConversationsBoardTable.tsx    # KEEP (deprecated)
|   |-- DeleteConfirmModal.tsx         # KEEP (existing)
|   |-- TitleEditor.tsx                # KEEP (existing)
|   |-- ViewModeTabs.tsx               # KEEP (existing)
|   |-- IdeationQueueHeader.tsx        # NEW
|   |-- IdeationQueueList.tsx          # NEW (was Table)
|   |-- IdeationQueueCard.tsx          # NEW (was Row)
|   |-- IdeationQueueFilters.tsx       # NEW
|   +-- IdeationQueueEmpty.tsx         # NEW
|
|-- hooks/
|   |-- useConversationActions.ts      # KEEP (existing)
|   +-- useConversationsFilter.ts      # MODIFY
|
|-- context/
|   +-- ConversationContext.tsx        # KEEP (existing)
|
|-- types/
|   +-- ideation-queue.types.ts        # NEW
|
|-- utils/
|   +-- ideation-queue-utils.ts        # NEW
|
+-- index.ts                           # MODIFY
```

---

## Component Hierarchy

```
ConversationsPage (page.tsx)
|
+-- IdeationQueueHeader
|   |-- Title section (icon + "Ideation Queue" + count)
|   +-- Controls section
|       |-- IdeationQueueFilters (status filter buttons)
|       +-- Search input
|
+-- IdeationQueueList
    |-- CSS Grid (responsive: 1/2/3 columns)
    |   +-- IdeationQueueCard (mapped for each conversation)
    |       |-- Card header: Status badge + Title (line-clamp-2)
    |       |-- Card body: Abstract preview (line-clamp-3)
    |       |-- Card footer: Created/Updated dates
    |       +-- [Entire card is clickable link]
    |
    +-- IdeationQueueEmpty (when no results)
```

### Card Layout Structure

```
+-------------------------------------------------------+
| [Status Badge]                                        |
| Title (line-clamp-2, font-semibold)                  |
|-------------------------------------------------------|
| Abstract preview text that can span multiple lines    |
| and will be truncated with line-clamp-3 to keep       |
| cards at a reasonable height...                       |
|-------------------------------------------------------|
| [Clock icon] Created 2 hours ago    Updated 1 hour ago|
+-------------------------------------------------------+
```

### Responsive Grid Behavior

```css
/* Mobile (< 768px): 1 column */
grid-cols-1

/* Tablet (>= 768px): 2 columns */
md:grid-cols-2

/* Desktop (>= 1024px): 3 columns */
lg:grid-cols-3

/* Gap between cards */
gap-4
```

---

## Type Definitions

### `types/ideation-queue.types.ts`

```typescript
import type { ComponentType } from "react";

/**
 * Status types for ideation queue items
 * Ordered by workflow progression for sorting
 */
export type IdeaStatus =
  | "no_idea"        // No ideaTitle/ideaAbstract present
  | "pending_launch" // Has idea but no research run (MVP: default if has idea)
  | "in_research"    // Active research run (future: from backend)
  | "completed"      // Research completed (future: from backend)
  | "failed";        // Research failed (future: from backend)

/**
 * Filter options including "all" for showing everything
 */
export type StatusFilterOption = "all" | IdeaStatus;

/**
 * Configuration for status badge styling (OCP-compliant)
 */
export interface IdeaStatusConfig {
  label: string;
  className: string;
  icon: ComponentType<{ className?: string }>;
}

/**
 * Configuration for filter button styling (OCP-compliant)
 */
export interface StatusFilterConfig {
  label: string;
  activeClass: string;
}

/**
 * Sort options for ideation queue
 */
export type IdeationSortKey = "newest" | "oldest" | "title_asc" | "title_desc" | "status";

/**
 * Props for IdeationQueueCard component (ISP-compliant: focused interface)
 */
export interface IdeationQueueCardProps {
  id: number;
  title: string;
  abstract: string | null;
  status: IdeaStatus;
  createdAt: string;
  updatedAt: string;
}

/**
 * Props for IdeationQueueFilters component
 */
export interface IdeationQueueFiltersProps {
  activeFilter: StatusFilterOption;
  onFilterChange: (filter: StatusFilterOption) => void;
}

/**
 * Extended return type for useConversationsFilter hook
 */
export interface UseConversationsFilterReturn {
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  statusFilter: StatusFilterOption;
  setStatusFilter: (filter: StatusFilterOption) => void;
  filteredConversations: Conversation[];
}
```

### Type Import Reference

```typescript
// In components that need these types:
import type {
  IdeaStatus,
  StatusFilterOption,
  IdeaStatusConfig,
  StatusFilterConfig,
  IdeationQueueCardProps,
  IdeationQueueFiltersProps,
} from "../types/ideation-queue.types";
```

---

## Interface Definitions (for DIP)

### Frontend Abstractions

```typescript
// types/ideation-queue.types.ts

/**
 * Abstraction for status derivation - allows different implementations
 * (MVP: client-side derivation, Future: backend-provided status)
 */
export interface StatusDerivation {
  deriveStatus: (conversation: Conversation) => IdeaStatus;
}

/**
 * Default implementation: derives status from Conversation fields
 */
export const defaultStatusDerivation: StatusDerivation = {
  deriveStatus: (conversation) => {
    // MVP: Simple check based on available fields
    if (!conversation.ideaTitle && !conversation.ideaAbstract) {
      return "no_idea";
    }
    // Without backend research status, default to pending
    return "pending_launch";
  },
};

/**
 * Future implementation: uses backend-provided status
 * (When API includes latest_research_status field)
 */
// export const backendStatusDerivation: StatusDerivation = {
//   deriveStatus: (conversation) => {
//     if (conversation.latestResearchStatus) {
//       return mapResearchStatus(conversation.latestResearchStatus);
//     }
//     return defaultStatusDerivation.deriveStatus(conversation);
//   },
// };
```

---

## Component Specifications

### 1. IdeationQueueHeader

**Single Responsibility**: Page header with title, counts, and filter controls.

**Props Interface**:
```typescript
interface IdeationQueueHeaderProps {
  searchTerm: string;
  onSearchChange: (term: string) => void;
  statusFilter: StatusFilterOption;
  onStatusFilterChange: (filter: StatusFilterOption) => void;
  totalCount: number;
  filteredCount: number;
}
```

**Dependencies**:
- `cn()` from `@/shared/lib/utils`
- `Search`, `Lightbulb` from `lucide-react`
- `IdeationQueueFilters` (child component)

**Extensibility (OCP)**: Filter options defined externally; header doesn't know about specific statuses.

---

### 2. IdeationQueueFilters

**Single Responsibility**: Render status filter buttons based on configuration.

**Props Interface**:
```typescript
interface IdeationQueueFiltersProps {
  activeFilter: StatusFilterOption;
  onFilterChange: (filter: StatusFilterOption) => void;
}
```

**Dependencies**:
- `cn()` from `@/shared/lib/utils`
- `STATUS_FILTER_OPTIONS` and `STATUS_FILTER_CONFIG` from utils

**Extensibility (OCP)**: New status filters added by updating config constant, not component code.

---

### 3. IdeationQueueList (was IdeationQueueTable)

**Single Responsibility**: Container for card grid layout and empty state handling.

**Props Interface**:
```typescript
interface IdeationQueueListProps {
  conversations: Conversation[];
  emptyMessage?: string;
}
```

**Dependencies**:
- `IdeationQueueCard` (child component)
- `IdeationQueueEmpty` (child component)
- `deriveIdeaStatus()` from utils

**Layout Implementation**:
```tsx
<div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
  {conversations.map((conversation) => (
    <IdeationQueueCard
      key={conversation.id}
      id={conversation.id}
      title={conversation.ideaTitle || conversation.title || "Untitled"}
      abstract={conversation.ideaAbstract}
      status={deriveIdeaStatus(conversation)}
      createdAt={conversation.createdAt}
      updatedAt={conversation.updatedAt}
    />
  ))}
</div>
```

**Extensibility (OCP)**: Card rendering delegated to `IdeationQueueCard`; list doesn't know about card internals.

---

### 4. IdeationQueueCard (was IdeationQueueRow)

**Single Responsibility**: Render a single conversation card with status, title, abstract, dates, and click action.

**Props Interface**:
```typescript
interface IdeationQueueCardProps {
  id: number;
  title: string;
  abstract: string | null;
  status: IdeaStatus;
  createdAt: string;
  updatedAt: string;
}
```

**Dependencies**:
- `getIdeaStatusBadge()` from utils
- `formatRelativeTime()` from `@/shared/lib/date-utils`
- `cn()` from `@/shared/lib/utils`
- `Clock` from `lucide-react`
- `Link` from `next/link`

**Card Structure**:
```tsx
<Link href={`/conversations/${id}`}>
  <article className="group rounded-xl border border-slate-800 bg-slate-900/50 p-4 transition-all hover:border-slate-700 hover:bg-slate-900/80">
    {/* Header: Status badge + Title */}
    <div className="mb-3 flex flex-wrap items-start gap-2">
      {getIdeaStatusBadge(status)}
      <h3 className="line-clamp-2 text-sm font-semibold text-slate-100">
        {title}
      </h3>
    </div>

    {/* Body: Abstract preview */}
    {abstract && (
      <p className="mb-3 line-clamp-3 text-xs leading-relaxed text-slate-400">
        {abstract}
      </p>
    )}

    {/* Footer: Dates */}
    <div className="flex flex-wrap items-center gap-3 text-[10px] uppercase tracking-wide text-slate-500">
      <span className="inline-flex items-center gap-1">
        <Clock className="h-3 w-3" />
        Created {formatRelativeTime(createdAt)}
      </span>
      <span>Updated {formatRelativeTime(updatedAt)}</span>
    </div>
  </article>
</Link>
```

**Extensibility (OCP)**:
- Status badge rendering delegated to utility function
- Card content sections are independent - new sections can be added without affecting existing ones
- Future additions (tags, action buttons, progress) fit naturally in the card structure

---

### 5. IdeationQueueEmpty

**Single Responsibility**: Display empty state message.

**Props Interface**:
```typescript
interface IdeationQueueEmptyProps {
  hasFilters?: boolean;
}
```

**Dependencies**:
- `Lightbulb` from `lucide-react`

**Extensibility (OCP)**: Message varies based on filter state via prop.

---

## Utility Specifications

### `utils/ideation-queue-utils.ts`

```typescript
import type { ReactNode } from "react";
import { CheckCircle2, Clock, Loader2, AlertCircle, FileQuestion } from "lucide-react";
import type { Conversation } from "@/shared/lib/api-adapters";
import type {
  IdeaStatus,
  StatusFilterOption,
  IdeaStatusConfig,
  StatusFilterConfig
} from "../types/ideation-queue.types";

// ===== Status Badge Configuration (OCP: extend by adding entries) =====

export const IDEA_STATUS_CONFIG: Record<IdeaStatus, IdeaStatusConfig> = {
  no_idea: {
    label: "No idea",
    className: "bg-slate-500/15 text-slate-400",
    icon: FileQuestion,
  },
  pending_launch: {
    label: "Pending",
    className: "bg-amber-500/15 text-amber-400",
    icon: Clock,
  },
  in_research: {
    label: "Running",
    className: "bg-sky-500/15 text-sky-400",
    icon: Loader2,
  },
  completed: {
    label: "Completed",
    className: "bg-emerald-500/15 text-emerald-400",
    icon: CheckCircle2,
  },
  failed: {
    label: "Failed",
    className: "bg-red-500/15 text-red-400",
    icon: AlertCircle,
  },
};

// ===== Filter Configuration (OCP: extend by adding entries) =====

export const STATUS_FILTER_OPTIONS: StatusFilterOption[] = [
  "all",
  "no_idea",
  "pending_launch",
  "in_research",
  "completed",
  "failed",
];

export const STATUS_FILTER_CONFIG: Record<StatusFilterOption, StatusFilterConfig> = {
  all: { label: "All", activeClass: "bg-slate-500/15 text-slate-300" },
  no_idea: { label: "No idea", activeClass: "bg-slate-500/15 text-slate-400" },
  pending_launch: { label: "Pending", activeClass: "bg-amber-500/15 text-amber-400" },
  in_research: { label: "Running", activeClass: "bg-sky-500/15 text-sky-400" },
  completed: { label: "Completed", activeClass: "bg-emerald-500/15 text-emerald-400" },
  failed: { label: "Failed", activeClass: "bg-red-500/15 text-red-400" },
};

// ===== Status Derivation =====

/**
 * Derives idea status from Conversation fields
 * MVP: Based on ideaTitle/ideaAbstract presence
 * Future: Will use backend-provided status
 */
export function deriveIdeaStatus(conversation: Conversation): IdeaStatus {
  // Check if conversation has an idea
  if (!conversation.ideaTitle && !conversation.ideaAbstract) {
    return "no_idea";
  }

  // MVP: Default to pending_launch for conversations with ideas
  // Future: Check conversation.latestResearchStatus when available
  return "pending_launch";
}

// ===== Badge Rendering =====

/**
 * Returns a styled status badge for an idea status
 * @param status - Idea status
 * @returns React element with styled badge
 */
export function getIdeaStatusBadge(status: IdeaStatus): ReactNode {
  const config = IDEA_STATUS_CONFIG[status];
  const Icon = config.icon;
  const isSpinning = status === "in_research";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium ${config.className}`}
    >
      <Icon className={`h-3.5 w-3.5 ${isSpinning ? "animate-spin" : ""}`} />
      {config.label}
    </span>
  );
}

// ===== Text Utilities =====

/**
 * Truncates text to a maximum length with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length (default: 200)
 * @returns Truncated text with ellipsis if needed
 */
export function truncateText(text: string, maxLength = 200): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trim()}...`;
}
```

---

## Hook Extension

### Extended `useConversationsFilter.ts`

```typescript
"use client";

import { useMemo, useState, useCallback } from "react";
import type { Conversation } from "@/shared/lib/api-adapters";
import type { StatusFilterOption, UseConversationsFilterReturn } from "../types/ideation-queue.types";
import { deriveIdeaStatus } from "../utils/ideation-queue-utils";

export function useConversationsFilter(
  conversations: Conversation[]
): UseConversationsFilterReturn {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilterOption>("all");

  const handleSetSearchTerm = useCallback((term: string) => {
    setSearchTerm(term);
  }, []);

  const handleSetStatusFilter = useCallback((filter: StatusFilterOption) => {
    setStatusFilter(filter);
  }, []);

  const filteredConversations = useMemo(() => {
    let filtered = conversations;

    // Apply status filter
    if (statusFilter !== "all") {
      filtered = filtered.filter(conversation => {
        const status = deriveIdeaStatus(conversation);
        return status === statusFilter;
      });
    }

    // Apply search filter
    if (searchTerm.trim()) {
      const lowerSearch = searchTerm.toLowerCase();
      filtered = filtered.filter(conversation => {
        const title = conversation.title?.toLowerCase() || "";
        const ideaTitle = conversation.ideaTitle?.toLowerCase() || "";
        const ideaAbstract = conversation.ideaAbstract?.toLowerCase() || "";
        const userName = conversation.userName?.toLowerCase() || "";
        const userEmail = conversation.userEmail?.toLowerCase() || "";

        return (
          title.includes(lowerSearch) ||
          ideaTitle.includes(lowerSearch) ||
          ideaAbstract.includes(lowerSearch) ||
          userName.includes(lowerSearch) ||
          userEmail.includes(lowerSearch)
        );
      });
    }

    return filtered;
  }, [conversations, searchTerm, statusFilter]);

  return {
    searchTerm,
    setSearchTerm: handleSetSearchTerm,
    statusFilter,
    setStatusFilter: handleSetStatusFilter,
    filteredConversations,
  };
}
```

---

## Integration Plan

### Step 1: Create Types (Phase 1)
1. Create `frontend/src/features/conversation/types/ideation-queue.types.ts`
2. Define all type interfaces

### Step 2: Create Utilities (Phase 1)
1. Create `frontend/src/features/conversation/utils/ideation-queue-utils.ts`
2. Implement `IDEA_STATUS_CONFIG`, `STATUS_FILTER_CONFIG`
3. Implement `deriveIdeaStatus()`, `getIdeaStatusBadge()`, `truncateText()`

### Step 3: Extend Hook (Phase 3)
1. Modify `frontend/src/features/conversation/hooks/useConversationsFilter.ts`
2. Add `statusFilter` state and filtering logic
3. Update return type interface

### Step 4: Create Components (Phase 2)
Order of implementation (dependencies first):
1. `IdeationQueueEmpty.tsx` - No dependencies on other new components
2. `IdeationQueueFilters.tsx` - Depends only on utils
3. **`IdeationQueueCard.tsx`** - Depends on utils (was Row)
4. **`IdeationQueueList.tsx`** - Depends on Card and Empty (was Table)
5. `IdeationQueueHeader.tsx` - Depends on Filters

### Step 5: Update Page (Phase 4)
1. Modify `frontend/src/app/(dashboard)/conversations/page.tsx`
2. Replace old components with new ones
3. Use extended hook return values

### Step 6: Update Exports (Phase 4)
1. Modify `frontend/src/features/conversation/index.ts`
2. Add exports for all new components and hooks

---

## For Next Phase (Implementation)

### Recommended Implementation Order

1. **Types** (`types/ideation-queue.types.ts`) - Define contracts first
2. **Utilities** (`utils/ideation-queue-utils.ts`) - Business logic
3. **Empty state** (`IdeationQueueEmpty.tsx`) - Simplest component
4. **Filters** (`IdeationQueueFilters.tsx`) - Self-contained
5. **Card** (`IdeationQueueCard.tsx`) - Individual item rendering (was Row)
6. **Hook extension** (`useConversationsFilter.ts`) - Add status filtering
7. **List** (`IdeationQueueList.tsx`) - Container with cards (was Table)
8. **Header** (`IdeationQueueHeader.tsx`) - Full header with controls
9. **Page update** (`page.tsx`) - Final integration
10. **Index update** (`index.ts`) - Export new components

### Type Dependencies

```
ideation-queue.types.ts (defines IdeaStatus, configs)
         |
         v
ideation-queue-utils.ts (uses types, implements logic)
         |
         +---> IdeationQueueFilters (uses STATUS_FILTER_*)
         +---> IdeationQueueCard (uses getIdeaStatusBadge)
         +---> IdeationQueueList (uses deriveIdeaStatus)
         +---> useConversationsFilter (uses deriveIdeaStatus)
```

### SOLID Considerations for Implementation

1. **SRP**: Keep each file focused - one component per file, one responsibility per function
2. **OCP**: Use the config constants (`IDEA_STATUS_CONFIG`, `STATUS_FILTER_CONFIG`) - do not hardcode switch statements. **Card layout inherently supports OCP** - adding new fields doesn't require restructuring.
3. **LSP**: Ensure `useConversationsFilter` maintains backward compatibility - existing code should still work
4. **ISP**: Component props should only include what's needed - avoid passing entire `Conversation` to `IdeationQueueCard`
5. **DIP**: Components receive data via props - do not call `useDashboard()` inside list or card components

### Refactoring Prerequisites

None required before feature work. Minor refactoring can happen during implementation:
- Use `formatRelativeTime` from shared utils instead of local function
- Keep old components working (don't modify `ConversationsBoardTable.tsx`)

### Critical Considerations

1. **Tailwind v4**: Use explicit class names only - the config objects satisfy this requirement
2. **No index.ts barrel exports**: Import directly from source files in page.tsx
3. **TypeScript strict mode**: All props interfaces must be complete
4. **Accessibility**:
   - Filter buttons need `aria-pressed` state
   - Cards should use `<article>` element
   - Ensure focus states are visible for keyboard navigation
5. **Responsive design**:
   - Grid columns: 1 (mobile) / 2 (md) / 3 (lg)
   - Gap: 4 (16px)
   - Card content uses `line-clamp-*` for consistent heights

---

## Approval Status

- [x] Pending approval
- [ ] Approved - proceed to Implementation
- [ ] Modified - see feedback below

### Feedback
{User feedback if modifications requested}

---

## Summary

```
FILES TO CREATE: 7
  - types/ideation-queue.types.ts
  - utils/ideation-queue-utils.ts
  - components/IdeationQueueHeader.tsx
  - components/IdeationQueueList.tsx    (was Table)
  - components/IdeationQueueCard.tsx    (was Row)
  - components/IdeationQueueFilters.tsx
  - components/IdeationQueueEmpty.tsx

FILES TO MODIFY: 3
  - hooks/useConversationsFilter.ts (extend with statusFilter)
  - index.ts (add exports)
  - page.tsx (use new components)

REUSED ASSETS: 10+
  - cn(), formatRelativeTime(), useDashboard(), useConversationsFilter()
  - Button, Tooltip components
  - Conversation type
  - Lucide icons (Lightbulb, Clock, Loader2, CheckCircle2, AlertCircle, FileQuestion, Search)

SOLID COMPLIANCE:
  - SRP: Separate files for types, utils, and each component
  - OCP: Config-driven badge/filter styling + card layout for easy extension
  - LSP: Hook extension maintains backward compatibility
  - ISP: Focused props interfaces for each component
  - DIP: Data passed via props, not fetched internally

LAYOUT CHANGES:
  - Table -> Card grid
  - Responsive: 1 col (mobile) / 2 cols (md) / 3 cols (lg)
  - Card reference: ResearchHistoryCard.tsx pattern
  - Entire card clickable (Link wrapper)
```

---

**APPROVAL REQUIRED**

Please review the updated architecture above. Key changes from previous version:

1. **Layout**: Table replaced with responsive card grid
2. **Components renamed**: `IdeationQueueTable` -> `IdeationQueueList`, `IdeationQueueRow` -> `IdeationQueueCard`
3. **Card structure**: Badge + title header, abstract body, dates footer
4. **Responsive grid**: 1/2/3 columns at mobile/tablet/desktop
5. **Full card clickable**: Follows `ResearchHistoryCard` pattern
6. **OCP improved**: Cards naturally support adding new fields without restructuring

Reply with:
- **"proceed"** or **"yes"** - Continue to Implementation phase
- **"modify: [your feedback]"** - I'll adjust the architecture
- **"elaborate"** - Provide more details and context for review
- **"stop"** - Pause here (progress saved in PRD)

Waiting for your approval before continuing...
