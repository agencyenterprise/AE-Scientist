# Next.js 15.4.8 Guidance for Ideation Queue

## Agent
nextjs-expert

## Timestamp
2025-12-05 15:00

---

## Detected Configuration

### Package Versions

| Package | Version | Notes |
|---------|---------|-------|
| `next` | 15.4.8 | App Router (default), Turbopack enabled for dev |
| `react` | 19.1.2 | Server Components supported, new hooks available |
| `react-dom` | 19.1.2 | Latest React 19 DOM implementation |
| `typescript` | ^5 | Strict mode with modern type inference |
| `@tanstack/react-query` | 5.90.10 | NOT used for conversations (uses DashboardContext) |
| `zustand` | 5.0.8 | Available for client state if needed |
| `tailwindcss` | ^4 | v4 requires explicit class names |
| `date-fns` | 4.1.0 | Date formatting utilities |
| `lucide-react` | 0.554.0 | Icon library |

### Router Type
**App Router** - Confirmed by:
- File path: `app/(dashboard)/conversations/page.tsx`
- Uses `"use client"` directive pattern
- No `pages/` directory for this route

### Key Configuration (next.config.ts)
- Standard configuration with image remote patterns
- No experimental features enabled
- Turbopack enabled in dev script (`next dev --turbopack`)

---

## Component Architecture: Server vs Client

### Current Page Pattern

The existing `conversations/page.tsx` uses `"use client"` because it:
1. Uses the `useDashboard()` context hook
2. Uses the `useConversationsFilter()` hook with `useState`
3. Has interactive search input

**This pattern is correct for this feature** - the page needs to remain a Client Component.

### Component Classification for Ideation Queue

| Component | Type | Directive | Reason |
|-----------|------|-----------|--------|
| `page.tsx` | Client | `"use client"` | Uses hooks (useDashboard, useConversationsFilter) |
| `IdeationQueueHeader` | Client | `"use client"` | Contains search input with onChange, receives callbacks |
| `IdeationQueueFilters` | Client | `"use client"` | Interactive filter buttons with onClick |
| `IdeationQueueList` | Client | `"use client"` | Part of client component tree (receives filtered data) |
| `IdeationQueueCard` | Client | `"use client"` | Part of client component tree, uses Link navigation |
| `IdeationQueueEmpty` | Client | `"use client"` | Part of client component tree |
| `ideation-queue-utils.ts` | N/A | None | Pure utility functions (no React) |
| `ideation-queue.types.ts` | N/A | None | TypeScript types only |

**Key Decision**: All components in this feature are Client Components because:
1. The page-level data comes from `useDashboard()` context
2. Filter state is managed with `useState`
3. All components are children of the client boundary set at page level

### When Server Components Would Be Used

For this project, Server Components would be appropriate if:
- Data was fetched directly in the component (e.g., `fetch()` with `cache`)
- No interactive state was needed
- Components were independent of client context

**This feature does not fit that pattern** because conversations data flows through the DashboardContext, which is a client-side context provider.

---

## Data Fetching Patterns

### Current Pattern (Correct for This Feature)

```typescript
// app/(dashboard)/conversations/page.tsx
"use client";

import { useDashboard } from "@/features/dashboard/contexts/DashboardContext";
import { useConversationsFilter } from "@/features/conversation/hooks/useConversationsFilter";

export default function ConversationsPage() {
  const { conversations } = useDashboard(); // Data from context
  const { searchTerm, setSearchTerm, statusFilter, setStatusFilter, filteredConversations } =
    useConversationsFilter(conversations);

  // ... render components
}
```

**Why This Is Correct:**
- `useDashboard()` manages data fetching centrally (React Query internally)
- Avoids duplicate API calls across pages
- Provides consistent data state across the dashboard
- Enables optimistic updates and caching at the context level

### Alternative Pattern (NOT Recommended for This Feature)

```typescript
// Server Component pattern - DO NOT USE for this feature
export default async function ConversationsPage() {
  const conversations = await fetch('/api/conversations', {
    next: { revalidate: 60 }
  }).then(r => r.json());

  return <IdeationQueueList conversations={conversations} />;
}
```

**Why NOT to use this:**
- Would duplicate data fetching (DashboardContext already fetches)
- Would lose real-time updates from context
- Would require separate cache invalidation logic
- Inconsistent with rest of dashboard architecture

---

## React 19 Patterns

### Hooks Available in React 19.1.2

| Hook | Use Case | Recommended for This Feature? |
|------|----------|------------------------------|
| `useState` | Local component state | Yes - for filter and search state |
| `useMemo` | Memoize expensive computations | Yes - for filtered results |
| `useCallback` | Stable function references | Yes - for setters passed to children |
| `useOptimistic` | Optimistic UI updates | No - not modifying data, just filtering |
| `useTransition` | Non-blocking state updates | Maybe - for large list filtering |
| `use` | Read promises in render | No - data comes from context |

### Recommended Patterns

#### 1. Filter State with useCallback

```typescript
// hooks/useConversationsFilter.ts
"use client";

import { useMemo, useState, useCallback } from "react";

export function useConversationsFilter(conversations: Conversation[]) {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilterOption>("all");

  // Stable references for child components
  const handleSetSearchTerm = useCallback((term: string) => {
    setSearchTerm(term);
  }, []);

  const handleSetStatusFilter = useCallback((filter: StatusFilterOption) => {
    setStatusFilter(filter);
  }, []);

  // Memoized filtering for performance
  const filteredConversations = useMemo(() => {
    let filtered = conversations;

    if (statusFilter !== "all") {
      filtered = filtered.filter(c => deriveIdeaStatus(c) === statusFilter);
    }

    if (searchTerm.trim()) {
      const lower = searchTerm.toLowerCase();
      filtered = filtered.filter(c =>
        c.title?.toLowerCase().includes(lower) ||
        c.ideaTitle?.toLowerCase().includes(lower)
      );
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

#### 2. Consider useTransition for Large Lists

If the conversations list becomes large (100+ items), consider `useTransition` for non-blocking filter updates:

```typescript
"use client";

import { useState, useTransition, useMemo } from "react";

export function useConversationsFilter(conversations: Conversation[]) {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilterOption>("all");
  const [isPending, startTransition] = useTransition();

  const handleSetSearchTerm = (term: string) => {
    // Immediate update for input responsiveness
    setSearchTerm(term);
  };

  const handleSetStatusFilter = (filter: StatusFilterOption) => {
    // Use transition for potentially expensive filter operation
    startTransition(() => {
      setStatusFilter(filter);
    });
  };

  // ... filtering logic

  return {
    // ...
    isPending, // Can show loading indicator during filter transition
  };
}
```

**Note**: For the current scope (typically <100 conversations), basic `useState` is sufficient. Add `useTransition` only if performance issues are observed.

---

## Performance Optimization

### Component Memoization

#### When to Use React.memo

| Component | Use React.memo? | Reason |
|-----------|-----------------|--------|
| `IdeationQueueCard` | **Yes** | Rendered in a list; props are simple primitives |
| `IdeationQueueFilters` | No | Few renders, simple props |
| `IdeationQueueHeader` | No | Re-renders are necessary for search input |
| `IdeationQueueList` | No | Parent of list; memoizing children is more effective |
| `IdeationQueueEmpty` | No | Conditionally rendered, simple component |

#### Card Memoization Example

```typescript
// components/IdeationQueueCard.tsx
"use client";

import { memo } from "react";
import Link from "next/link";
import type { IdeationQueueCardProps } from "../types/ideation-queue.types";
import { getIdeaStatusBadge } from "../utils/ideation-queue-utils";
import { formatRelativeTime } from "@/shared/lib/date-utils";

function IdeationQueueCardComponent({
  id,
  title,
  abstract,
  status,
  createdAt,
  updatedAt,
}: IdeationQueueCardProps) {
  return (
    <Link href={`/conversations/${id}`}>
      <article className="group rounded-xl border border-slate-800 bg-slate-900/50 p-4 transition-all hover:border-slate-700 hover:bg-slate-900/80">
        {/* Card content */}
      </article>
    </Link>
  );
}

// Memoize to prevent re-renders when parent filters change
export const IdeationQueueCard = memo(IdeationQueueCardComponent);
```

### List Rendering Optimization

#### Key Best Practices

1. **Use stable keys**: Use `conversation.id` (number), not array index

```typescript
// Good
{conversations.map((conv) => (
  <IdeationQueueCard key={conv.id} {...cardProps} />
))}

// Bad - causes unnecessary re-renders
{conversations.map((conv, index) => (
  <IdeationQueueCard key={index} {...cardProps} />
))}
```

2. **Avoid inline object creation in props**:

```typescript
// Bad - creates new object every render
<IdeationQueueCard
  style={{ marginBottom: 16 }}
  data={{ id: conv.id, title: conv.title }}
/>

// Good - extract to component level or memoize
<IdeationQueueCard
  id={conv.id}
  title={conv.title}
  abstract={conv.ideaAbstract}
  status={deriveIdeaStatus(conv)}
  createdAt={conv.createdAt}
  updatedAt={conv.updatedAt}
/>
```

3. **Compute derived data in parent**:

```typescript
// In IdeationQueueList.tsx
{conversations.map((conversation) => (
  <IdeationQueueCard
    key={conversation.id}
    id={conversation.id}
    title={conversation.ideaTitle || conversation.title || "Untitled"}
    abstract={conversation.ideaAbstract}
    status={deriveIdeaStatus(conversation)} // Computed once per render cycle
    createdAt={conversation.createdAt}
    updatedAt={conversation.updatedAt}
  />
))}
```

### Search Input Debouncing

For the search input, consider debouncing if typing causes lag:

```typescript
// In IdeationQueueHeader.tsx
"use client";

import { useState, useEffect } from "react";

interface Props {
  searchTerm: string;
  onSearchChange: (term: string) => void;
}

export function IdeationQueueHeader({ searchTerm, onSearchChange }: Props) {
  const [localSearch, setLocalSearch] = useState(searchTerm);

  // Debounce search updates
  useEffect(() => {
    const timer = setTimeout(() => {
      onSearchChange(localSearch);
    }, 300);

    return () => clearTimeout(timer);
  }, [localSearch, onSearchChange]);

  return (
    <input
      type="text"
      value={localSearch}
      onChange={(e) => setLocalSearch(e.target.value)}
      placeholder="Search ideas..."
      className="..."
    />
  );
}
```

**Note**: For this feature's scope, debouncing is optional. Implement if search responsiveness becomes an issue.

---

## Styling Patterns (Tailwind CSS v4)

### Critical: Explicit Class Names Only

Tailwind v4 requires explicit class names. Dynamic class construction is NOT supported:

```typescript
// BAD - Tailwind v4 won't detect these classes
const bgColor = status === "completed" ? "bg-emerald-500" : "bg-red-500";
<div className={bgColor}>...</div>

// GOOD - Use configuration objects with explicit classes
const IDEA_STATUS_CONFIG = {
  completed: {
    className: "bg-emerald-500/15 text-emerald-400",
  },
  failed: {
    className: "bg-red-500/15 text-red-400",
  },
  // ...
};

<div className={IDEA_STATUS_CONFIG[status].className}>...</div>
```

### Responsive Grid Layout for Cards

```typescript
// IdeationQueueList.tsx
<div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
  {/* Cards */}
</div>
```

| Breakpoint | Columns | Width |
|------------|---------|-------|
| Default (mobile) | 1 | < 768px |
| `md:` | 2 | >= 768px |
| `lg:` | 3 | >= 1024px |

### Card Hover States

```typescript
// IdeationQueueCard.tsx
<article className="group rounded-xl border border-slate-800 bg-slate-900/50 p-4 transition-all hover:border-slate-700 hover:bg-slate-900/80">
```

Transition classes breakdown:
- `transition-all` - Animates all property changes
- `hover:border-slate-700` - Lightens border on hover
- `hover:bg-slate-900/80` - Slightly more opaque background on hover

### Text Truncation

Use Tailwind's line-clamp utilities (included in Tailwind v4):

```typescript
// Title: 2 lines max
<h3 className="line-clamp-2 text-sm font-semibold text-slate-100">
  {title}
</h3>

// Abstract: 3 lines max
<p className="line-clamp-3 text-xs leading-relaxed text-slate-400">
  {abstract}
</p>
```

### Dark Mode

The project uses a dark theme by default (slate-900, slate-800 backgrounds). No light mode switching is implemented. Keep all styling dark-theme-consistent:

- Backgrounds: `bg-slate-900`, `bg-slate-950`, `bg-slate-900/50`
- Text: `text-slate-100` (primary), `text-slate-300` (secondary), `text-slate-500` (muted)
- Borders: `border-slate-800`, `border-slate-700`

---

## Type Safety

### Component Props Interfaces

Follow the ISP (Interface Segregation Principle) - pass only needed props:

```typescript
// types/ideation-queue.types.ts

/**
 * Props for IdeationQueueCard - focused interface, not entire Conversation
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
 * Props for IdeationQueueFilters
 */
export interface IdeationQueueFiltersProps {
  activeFilter: StatusFilterOption;
  onFilterChange: (filter: StatusFilterOption) => void;
}

/**
 * Props for IdeationQueueHeader
 */
export interface IdeationQueueHeaderProps {
  searchTerm: string;
  onSearchChange: (term: string) => void;
  statusFilter: StatusFilterOption;
  onStatusFilterChange: (filter: StatusFilterOption) => void;
  totalCount: number;
  filteredCount: number;
}
```

### Type Inference with Next.js 15

Next.js 15.4.8 has excellent TypeScript integration. Use type inference where possible:

```typescript
// Let TypeScript infer return type
export function useConversationsFilter(conversations: Conversation[]) {
  // ... implementation
  return {
    searchTerm,
    setSearchTerm: handleSetSearchTerm,
    statusFilter,
    setStatusFilter: handleSetStatusFilter,
    filteredConversations,
  };
}

// Type is automatically inferred as:
// {
//   searchTerm: string;
//   setSearchTerm: (term: string) => void;
//   statusFilter: StatusFilterOption;
//   setStatusFilter: (filter: StatusFilterOption) => void;
//   filteredConversations: Conversation[];
// }
```

### Import API Types

The project generates API types from OpenAPI spec. Use them:

```typescript
import type { Conversation } from "@/shared/lib/api-adapters";
```

---

## Common Pitfalls to Avoid

### 1. Hydration Mismatches

**Problem**: Server and client render different content, causing hydration errors.

**In This Feature**: Not a major concern since all components are client-side rendered. However, avoid:

```typescript
// BAD - Different on server vs client
<span>{new Date().toLocaleString()}</span>

// GOOD - Use date-fns with consistent formatting
import { formatRelativeTime } from "@/shared/lib/date-utils";
<span>{formatRelativeTime(dateString)}</span>
```

### 2. Next.js 15 params/searchParams Promise

**In This Feature**: Not applicable - this page doesn't use dynamic route params or searchParams.

**General Note**: In Next.js 15, dynamic route `params` and `searchParams` are now Promises:

```typescript
// Next.js 15 pattern for dynamic routes (NOT used in this feature)
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  // ...
}
```

### 3. Client/Server Boundary Issues

**Problem**: Trying to use hooks in Server Components or passing non-serializable props across the boundary.

**In This Feature**: All components are Client Components, so this isn't a concern. But remember:
- `"use client"` directive only needs to be at the top-level client component
- Child components inherit the client boundary
- Utility functions (non-React) don't need the directive

### 4. Missing "use client" in Hook Files

**Problem**: Hooks using React state/effects fail without "use client".

```typescript
// REQUIRED at top of hook files
"use client";

import { useState, useMemo, useCallback } from "react";
// ...
```

### 5. Dynamic Tailwind Classes in v4

**Problem**: Tailwind v4 doesn't detect dynamically constructed class names.

```typescript
// BAD
const colorClass = `bg-${color}-500`;

// GOOD - Define all classes explicitly
const COLOR_CLASSES = {
  emerald: "bg-emerald-500/15 text-emerald-400",
  amber: "bg-amber-500/15 text-amber-400",
  // ...
};
```

### 6. Stale Closures in Callbacks

**Problem**: Callbacks capture stale state values.

```typescript
// Potential issue if not using useCallback
const handleFilter = (filter) => {
  setStatusFilter(filter);
  console.log(statusFilter); // May log stale value
};

// Solution: use the parameter, not state
const handleFilter = useCallback((filter: StatusFilterOption) => {
  setStatusFilter(filter);
  // Use 'filter' parameter, not 'statusFilter' state
}, []);
```

---

## Testing Considerations

### Component Testing Patterns

```typescript
// Example test structure (if tests are added)
import { render, screen, fireEvent } from "@testing-library/react";
import { IdeationQueueCard } from "./IdeationQueueCard";

describe("IdeationQueueCard", () => {
  const defaultProps = {
    id: 1,
    title: "Test Hypothesis",
    abstract: "This is a test abstract",
    status: "pending_launch" as const,
    createdAt: "2025-01-01T00:00:00Z",
    updatedAt: "2025-01-02T00:00:00Z",
  };

  it("renders title and abstract", () => {
    render(<IdeationQueueCard {...defaultProps} />);
    expect(screen.getByText("Test Hypothesis")).toBeInTheDocument();
    expect(screen.getByText("This is a test abstract")).toBeInTheDocument();
  });

  it("displays correct status badge", () => {
    render(<IdeationQueueCard {...defaultProps} />);
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("links to conversation detail page", () => {
    render(<IdeationQueueCard {...defaultProps} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/conversations/1");
  });
});
```

### Integration Testing for Filtering

```typescript
describe("IdeationQueueFilters", () => {
  it("calls onFilterChange when filter button clicked", () => {
    const onFilterChange = jest.fn();
    render(
      <IdeationQueueFilters
        activeFilter="all"
        onFilterChange={onFilterChange}
      />
    );

    fireEvent.click(screen.getByText("Completed"));
    expect(onFilterChange).toHaveBeenCalledWith("completed");
  });
});
```

### Accessibility Testing

Ensure all interactive elements have proper ARIA attributes:

```typescript
// Filter buttons
<button
  type="button"
  aria-pressed={activeFilter === option}
  onClick={() => onFilterChange(option)}
  className={cn(/* ... */)}
>
  {label}
</button>

// Cards should be articles for semantic meaning
<article aria-labelledby={`card-title-${id}`}>
  <h3 id={`card-title-${id}`}>{title}</h3>
</article>

// Search input
<input
  type="search"
  role="searchbox"
  aria-label="Search ideas"
  placeholder="Search..."
/>
```

---

## Implementation Checklist

### Pre-Implementation

- [ ] Verify Next.js 15.4.8 is installed (`npm list next`)
- [ ] Verify React 19.1.2 is installed (`npm list react`)
- [ ] Review existing patterns in `ResearchHistoryCard.tsx`
- [ ] Review filter pattern in `research-logs-list.tsx`

### Phase 1: Types and Utilities

- [ ] Create `/frontend/src/features/conversation/types/ideation-queue.types.ts`
  - [ ] Define `IdeaStatus` type
  - [ ] Define `StatusFilterOption` type
  - [ ] Define `IdeaStatusConfig` interface
  - [ ] Define component props interfaces

- [ ] Create `/frontend/src/features/conversation/utils/ideation-queue-utils.ts`
  - [ ] Define `IDEA_STATUS_CONFIG` with explicit Tailwind classes
  - [ ] Define `STATUS_FILTER_CONFIG` with explicit Tailwind classes
  - [ ] Implement `deriveIdeaStatus()` function
  - [ ] Implement `getIdeaStatusBadge()` function

### Phase 2: Components

- [ ] Create `IdeationQueueEmpty.tsx`
  - [ ] Add `"use client"` directive
  - [ ] Follow `ResearchBoardEmpty` pattern

- [ ] Create `IdeationQueueFilters.tsx`
  - [ ] Add `"use client"` directive
  - [ ] Add `aria-pressed` for accessibility
  - [ ] Use explicit class names from config

- [ ] Create `IdeationQueueCard.tsx`
  - [ ] Add `"use client"` directive
  - [ ] Wrap with `React.memo`
  - [ ] Use `Link` from `next/link`
  - [ ] Apply `line-clamp-*` for truncation

- [ ] Create `IdeationQueueList.tsx`
  - [ ] Add `"use client"` directive
  - [ ] Implement responsive grid layout
  - [ ] Map cards with stable keys

- [ ] Create `IdeationQueueHeader.tsx`
  - [ ] Add `"use client"` directive
  - [ ] Include search input
  - [ ] Include filter buttons

### Phase 3: Hook Extension

- [ ] Modify `useConversationsFilter.ts`
  - [ ] Add `statusFilter` state
  - [ ] Add status filtering to `useMemo`
  - [ ] Export new return values
  - [ ] Use `useCallback` for setters

### Phase 4: Page Integration

- [ ] Modify `page.tsx`
  - [ ] Import new components
  - [ ] Destructure new values from hook
  - [ ] Pass props to new components

- [ ] Modify `index.ts`
  - [ ] Export new components
  - [ ] Export new types

### Post-Implementation

- [ ] Test filtering by status
- [ ] Test search functionality
- [ ] Test responsive layout (mobile, tablet, desktop)
- [ ] Test keyboard navigation
- [ ] Verify no console errors/warnings
- [ ] Verify TypeScript compilation succeeds

---

## Documentation References

### Official Documentation
- [Next.js App Router](https://nextjs.org/docs/app)
- [Server Components](https://nextjs.org/docs/app/building-your-application/rendering/server-components)
- [Client Components](https://nextjs.org/docs/app/building-your-application/rendering/client-components)
- [React 19 Release Notes](https://react.dev/blog/2024/12/05/react-19)

### Breaking Changes
- [Next.js 15 params/searchParams Promise](https://github.com/vercel/next.js/issues/70899)
- [Handling Async Params](https://medium.com/@matijazib/handling-breaking-changes-in-next-js-15-async-params-and-search-params-96075e04f7b6)

### React 19 Features
- [useOptimistic Hook](https://react.dev/reference/react/useOptimistic)
- [useTransition Hook](https://react.dev/reference/react/useTransition)
- [React 19 Complete Guide](https://www.callstack.com/blog/the-complete-developer-guide-to-react-19-part-1-async-handling)

---

## For Executor

### Key Points to Follow

1. **All components are Client Components** - Add `"use client"` to every `.tsx` file in this feature
2. **Use explicit Tailwind classes** - No dynamic class construction; use config objects
3. **Reuse existing utilities** - `cn()`, `formatRelativeTime()`, existing patterns
4. **Follow ISP** - Pass focused props to components, not entire Conversation objects
5. **Memoize cards** - Use `React.memo` on `IdeationQueueCard` for list performance
6. **Use stable keys** - Always use `conversation.id` as key in list rendering
7. **Accessibility** - Add `aria-pressed` to filter buttons, semantic HTML

### Quick Reference: Component Structure

```
features/conversation/
  types/
    ideation-queue.types.ts    # Types only, no directive needed
  utils/
    ideation-queue-utils.ts    # Utilities only, no directive needed
  components/
    IdeationQueueHeader.tsx    # "use client"
    IdeationQueueFilters.tsx   # "use client"
    IdeationQueueList.tsx      # "use client"
    IdeationQueueCard.tsx      # "use client" + React.memo
    IdeationQueueEmpty.tsx     # "use client"
  hooks/
    useConversationsFilter.ts  # "use client" (existing, extend)
```

### Import Template

```typescript
// Standard imports for Ideation Queue components
"use client";

import { memo } from "react"; // Only in Card component
import Link from "next/link";
import { cn } from "@/shared/lib/utils";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { Lightbulb, Clock, Search } from "lucide-react";
import type { Conversation } from "@/shared/lib/api-adapters";
import type { IdeaStatus, StatusFilterOption } from "../types/ideation-queue.types";
import { getIdeaStatusBadge, deriveIdeaStatus, STATUS_FILTER_CONFIG } from "../utils/ideation-queue-utils";
```

---

## Approval Status

- [x] Analysis Complete
- [ ] Approved - proceed to Implementation
- [ ] Modified - see feedback below

---

**APPROVAL REQUIRED**

Please review the Next.js 15.4.8 guidance above. This document covers:

1. **Component Architecture** - All Client Components due to DashboardContext pattern
2. **React 19 Patterns** - Hooks usage, memoization strategies
3. **Performance** - Card memoization, list rendering, optional debouncing
4. **Tailwind v4** - Explicit class names, responsive grid
5. **Type Safety** - Focused interfaces, TypeScript best practices
6. **Common Pitfalls** - Hydration, closures, dynamic classes
7. **Implementation Checklist** - Step-by-step guidance for executor

Reply with:
- **"proceed"** or **"yes"** - Guidance is correct, continue to implementation
- **"modify: [your feedback]"** - I'll adjust the recommendations
- **"elaborate: [topic]"** - Provide more details on a specific topic
- **"stop"** - Pause here

Waiting for your approval...
