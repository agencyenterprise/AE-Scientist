# Next.js 15 Technical Guidance

## Agent
nextjs-15-expert

## Timestamp
2025-12-08

## Project Analysis

### Version Verification

**CONFIRMED**: This is a Next.js 15.x project.

### Detected Versions

| Package | Version | Notes |
|---------|---------|-------|
| next | 15.4.8 | App Router, Turbopack enabled for dev |
| react | 19.1.2 | React 19 (stable with Next.js 15) |
| typescript | ^5 | TypeScript 5.x |
| @tanstack/react-query | ^5.90.10 | React Query v5 for data fetching |
| zustand | ^5.0.8 | State management (not used for this feature) |
| tailwindcss | ^4 | Tailwind CSS v4 |

### Router Type
App Router (confirmed from `frontend/src/app/(dashboard)/conversations/` structure)

### Key Configuration
- **Turbopack**: Enabled for development (`next dev --turbopack`)
- **Image optimization**: Configured for localhost and Railway domains
- **API types**: Auto-generated from OpenAPI schema (`api.gen.ts`)

---

## 1. Component Directive Strategy

### Where to Place `'use client'`

Based on Next.js 15 best practices, place `'use client'` **only at the entry point** of client-side component trees:

```
IdeationQueueCard.tsx        -> 'use client' (EXISTING - already has it)
  |
  +-- IdeationQueueRunsList.tsx  -> NO directive needed (imported by client component)
        |
        +-- IdeationQueueRunItem.tsx  -> NO directive needed

useConversationResearchRuns.ts -> 'use client' (uses React Query hooks)
```

### Directive Placement Rules for This Feature

| File | Directive | Reason |
|------|-----------|--------|
| `IdeationQueueCard.tsx` | `'use client'` | Already exists - uses `useState`, `useRouter` |
| `IdeationQueueRunsList.tsx` | **None** | Imported by client component, automatically client |
| `IdeationQueueRunItem.tsx` | **None** | Imported by client component, automatically client |
| `useConversationResearchRuns.ts` | `'use client'` | Uses `useQuery` hook (must be client-side) |
| `ideation-queue.types.ts` | **None** | Pure types, no runtime code |

### Minimizing Client Bundle Size

**Current Architecture is Already Optimal**

The conversations page (`page.tsx`) is already marked `'use client'` because it uses dashboard context. Since our new components are nested under `IdeationQueueCard` (which is already client-side), we don't add bundle overhead.

**Key Insight**: The boundary decision was already made at the page level. Our feature adds minimal additional client code because:
1. New components are children of existing client components
2. We reuse existing utilities (`getStatusBadge`, `truncateRunId`, `formatRelativeTime`)
3. No new dependencies are introduced

---

## 2. Data Fetching Patterns

### React Query Integration with Next.js 15

**Query Key Structure**:
```typescript
// Hierarchical key structure for proper cache invalidation
queryKey: ["conversation-research-runs", conversationId]

// This allows:
// - Invalidate all conversation runs: queryClient.invalidateQueries({ queryKey: ["conversation-research-runs"] })
// - Invalidate specific conversation: queryClient.invalidateQueries({ queryKey: ["conversation-research-runs", 123] })
```

**Caching Strategy**:
```typescript
export function useConversationResearchRuns(conversationId: number) {
  return useQuery({
    queryKey: ["conversation-research-runs", conversationId],
    queryFn: () => fetchConversationResearchRuns(conversationId),
    staleTime: 30 * 1000,    // 30 seconds - runs may change status
    gcTime: 5 * 60 * 1000,   // 5 minutes (formerly cacheTime in v4)
    // NOTE: No 'enabled' prop needed - hook is only called when card expands
  });
}
```

**Why These Values**:
- `staleTime: 30s` - Research runs can transition between states (pending -> running -> completed). Users expect to see updates when they re-expand a card.
- `gcTime: 5m` - Keep data in cache longer since user may collapse/expand cards while browsing.

### On-Demand Fetching Pattern

The architecture specifies fetching runs only when a card is expanded. This is implemented by **conditional rendering**, not `enabled` flag:

```typescript
// In IdeationQueueCard.tsx
{isExpanded && <IdeationQueueRunsList conversationId={id} />}
```

When `IdeationQueueRunsList` mounts, it calls the hook which triggers the fetch. When it unmounts (collapsed), the query remains in cache but stops refetching.

**Why Not Use `enabled` Prop?**

The `enabled` prop would require:
1. Calling the hook unconditionally (even when collapsed)
2. Tracking `isExpanded` state at the hook level

The conditional rendering approach is cleaner because:
1. Hook is only instantiated when needed
2. No wasted query subscriptions
3. Matches React's mental model (mount = fetch, unmount = cleanup)

### Prefetching Considerations

**Not recommended for this feature** because:
1. Users may have 50+ ideas - prefetching all would be expensive
2. Most users only care about runs for specific ideas
3. The API response is small and fast (~50ms)
4. React Query's cache already handles re-expansion instantly

If prefetching becomes needed later (e.g., hover intent), use:
```typescript
const queryClient = useQueryClient();

const handleHover = () => {
  queryClient.prefetchQuery({
    queryKey: ["conversation-research-runs", conversationId],
    queryFn: () => fetchConversationResearchRuns(conversationId),
    staleTime: 30 * 1000,
  });
};
```

---

## 3. Navigation Implementation

### Using `next/link` for Run Items

**Problem**: The run items need to navigate to `/research/{runId}`, but they're nested inside a clickable card that navigates to `/conversations/{id}`.

**Solution**: Use `useRouter` with `stopPropagation` instead of `<Link>`:

```typescript
// IdeationQueueRunItem.tsx
import { useRouter } from "next/navigation";  // NOT 'next/router'

export function IdeationQueueRunItem({ runId, ... }: Props) {
  const router = useRouter();

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();  // Prevent card navigation
    e.preventDefault();    // In case wrapped in any form
    router.push(`/research/${runId}`);
  };

  return (
    <button
      onClick={handleClick}
      type="button"
      className="..." // Full row styling
    >
      {/* Run content */}
    </button>
  );
}
```

**Why Not `<Link>`?**

Using `<Link>` inside a clickable card creates two issues:
1. Click events bubble up, triggering both navigations
2. `stopPropagation` on `<Link>` may interfere with its internal behavior

The `<button>` + `router.push` approach gives us full control over the click event.

### Preserving Scroll Position

Next.js 15 App Router preserves scroll position by default on back/forward navigation. No special handling needed.

However, when navigating from run item to research page:
```typescript
router.push(`/research/${runId}`);  // Scrolls to top by default
```

If we want to preserve scroll (uncommon for this UX):
```typescript
router.push(`/research/${runId}`, { scroll: false });
```

**Recommendation**: Use default behavior (scroll to top) since user is navigating to a completely different view.

### Route Transition Best Practices

**Add Loading State for Research Route** (optional enhancement):

If `/research/[runId]/page.tsx` is slow to render, add:
```typescript
// app/(dashboard)/research/[runId]/loading.tsx
export default function Loading() {
  return <ResearchDetailSkeleton />;
}
```

This enables Next.js 15's partial prefetching, showing the loading skeleton instantly while data loads.

---

## 4. State Management

### Local Expand/Collapse State

Use `useState` at the `IdeationQueueCard` level:

```typescript
// IdeationQueueCard.tsx
import { useState, memo } from "react";

function IdeationQueueCardComponent({ id, ... }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);
  const router = useRouter();

  const handleCardClick = () => {
    router.push(`/conversations/${id}`);
  };

  const handleExpandToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded((prev) => !prev);
  };

  return (
    <article onClick={handleCardClick} className="cursor-pointer ...">
      {/* Card content */}
      <button onClick={handleExpandToggle} type="button">
        {isExpanded ? <ChevronUp /> : <ChevronDown />}
      </button>

      {isExpanded && <IdeationQueueRunsList conversationId={id} />}
    </article>
  );
}
```

### State Persistence Across Navigation

**Issue**: When user navigates to `/conversations/{id}` and back, expand state is lost.

**Options**:

1. **Accept the reset** (Recommended)
   - Simplest approach
   - User expectation: returning to list = fresh view
   - React Query cache ensures runs load instantly on re-expand

2. **URL-based state** (If persistence needed)
   ```typescript
   // Not recommended for this feature - adds URL complexity
   const searchParams = useSearchParams();
   const expandedIds = searchParams.get('expanded')?.split(',') ?? [];
   ```

3. **Zustand store** (If many cards need persistence)
   ```typescript
   // Overkill for simple expand/collapse
   const { expandedCardIds, toggleCard } = useIdeationQueueStore();
   ```

**Recommendation**: Option 1 - Accept the reset. The expand state is transient UI state, not application state. Users expect lists to reset on navigation.

### Optimistic Updates

**Not needed for this feature** because:
1. We're only reading data (no mutations from this UI)
2. Run status changes come from backend processes, not user actions

If we later add "Cancel Run" functionality:
```typescript
const queryClient = useQueryClient();

const cancelRun = useMutation({
  mutationFn: (runId: string) => apiFetch(`/research-runs/${runId}/cancel`, { method: 'POST' }),
  onMutate: async (runId) => {
    // Cancel outgoing queries
    await queryClient.cancelQueries({ queryKey: ["conversation-research-runs", conversationId] });

    // Snapshot previous value
    const previous = queryClient.getQueryData(["conversation-research-runs", conversationId]);

    // Optimistically update
    queryClient.setQueryData(["conversation-research-runs", conversationId], (old) =>
      old?.map((run) => run.run_id === runId ? { ...run, status: "cancelled" } : run)
    );

    return { previous };
  },
  onError: (err, runId, context) => {
    // Rollback on error
    queryClient.setQueryData(["conversation-research-runs", conversationId], context?.previous);
  },
  onSettled: () => {
    // Refetch to ensure consistency
    queryClient.invalidateQueries({ queryKey: ["conversation-research-runs", conversationId] });
  },
});
```

---

## 5. Performance Optimization

### Code Splitting

**No dynamic imports needed** because:
1. `IdeationQueueRunsList` is conditionally rendered (already "split" by mount/unmount)
2. Components are small (~2KB each)
3. They're part of the same feature bundle as `IdeationQueueCard`

If components grow significantly:
```typescript
import dynamic from 'next/dynamic';

const IdeationQueueRunsList = dynamic(
  () => import('./IdeationQueueRunsList'),
  { loading: () => <RunsListSkeleton /> }
);
```

### Memoization Strategy

**Already Applied**:
- `IdeationQueueCard` is wrapped with `memo()` (existing code)

**Additional Memoization for New Components**:

```typescript
// IdeationQueueRunItem.tsx
import { memo } from "react";

function IdeationQueueRunItemComponent({ runId, status, ... }: Props) {
  // Implementation
}

export const IdeationQueueRunItem = memo(IdeationQueueRunItemComponent);
```

**When to Use `useCallback`/`useMemo`**:

```typescript
// In IdeationQueueCard - handleExpandToggle doesn't need useCallback
// because the card is already memoized and this handler is cheap
const handleExpandToggle = (e: React.MouseEvent) => {
  e.stopPropagation();
  setIsExpanded((prev) => !prev);
};

// DO use useCallback if passing to memoized child:
const handleRunClick = useCallback((runId: string) => {
  router.push(`/research/${runId}`);
}, [router]);
```

**Recommendation**: Keep it simple. Memoize components with `memo()`, avoid `useCallback`/`useMemo` unless profiling shows a need.

### List Rendering Optimization

The architecture limits displayed runs to 5 with "View all" link. This is good for:
1. DOM node count
2. Initial render time
3. Visual clarity

No virtualization needed for 5 items.

---

## 6. TypeScript with Next.js 15

### Import Path Conventions

**Use `@/` alias** for all imports (already configured in project):

```typescript
// Correct
import { apiFetch } from "@/shared/lib/api-client";
import type { ConversationResponse } from "@/types";

// Incorrect
import { apiFetch } from "../../../shared/lib/api-client";
```

### Type Safety for Navigation

```typescript
// Define route type for type-safe navigation
type ResearchRoute = `/research/${string}`;

const handleClick = (runId: string) => {
  const route: ResearchRoute = `/research/${runId}`;
  router.push(route);
};
```

### Props Typing Best Practices

**Derive types from API schema** (already planned in architecture):

```typescript
// In types file
import type { ConversationResponse } from "@/types";

// Derive from API response type
export type ResearchRunFromApi = NonNullable<ConversationResponse["research_runs"]>[number];

// Props interface for component
export interface IdeationQueueRunItemProps {
  runId: string;
  status: ResearchRunFromApi["status"];  // Type-safe status values
  gpuType: string | null;
  createdAt: string;
}
```

### Avoiding `any` Types

```typescript
// Bad
const handleClick = (e: any) => { ... }

// Good
const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
  e.stopPropagation();
  // ...
};
```

---

## 7. Code Examples

### Complete Hook Implementation

```typescript
// frontend/src/features/conversation/hooks/useConversationResearchRuns.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";
import type { ConversationResponse } from "@/types";

// Derive type from API schema
type ResearchRunSummary = NonNullable<ConversationResponse["research_runs"]>[number];

async function fetchConversationResearchRuns(
  conversationId: number
): Promise<ResearchRunSummary[]> {
  const data = await apiFetch<ConversationResponse>(
    `/conversations/${conversationId}`
  );
  // Sort by created_at descending (newest first)
  return (data.research_runs ?? []).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
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
    staleTime: 30 * 1000,  // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
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

### Complete Run Item Component

```typescript
// frontend/src/features/conversation/components/IdeationQueueRunItem.tsx
import { memo } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { getStatusBadge, truncateRunId } from "@/features/research/utils/research-utils";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { cn } from "@/shared/lib/utils";
import type { IdeationQueueRunItemProps } from "../types/ideation-queue.types";

function IdeationQueueRunItemComponent({
  runId,
  status,
  gpuType,
  createdAt,
}: IdeationQueueRunItemProps) {
  const router = useRouter();

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    e.preventDefault();
    router.push(`/research/${runId}`);
  };

  return (
    <button
      onClick={handleClick}
      type="button"
      className={cn(
        "flex w-full items-center justify-between gap-3",
        "rounded-lg border border-slate-800/50 bg-slate-900/30",
        "px-3 py-2 text-left",
        "transition-colors hover:border-slate-700 hover:bg-slate-800/50"
      )}
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

export const IdeationQueueRunItem = memo(IdeationQueueRunItemComponent);
```

### Card Modification Pattern

```typescript
// frontend/src/features/conversation/components/IdeationQueueCard.tsx
"use client";

import { memo, useState } from "react";
import { useRouter } from "next/navigation";
import { Clock, ChevronDown, ChevronUp } from "lucide-react";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { cn } from "@/shared/lib/utils";
import type { IdeationQueueCardProps } from "../types/ideation-queue.types";
import { getIdeaStatusBadge } from "../utils/ideation-queue-utils";
import { IdeationQueueRunsList } from "./IdeationQueueRunsList";

function IdeationQueueCardComponent({
  id,
  title,
  abstract,
  status,
  createdAt,
  updatedAt,
}: IdeationQueueCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const router = useRouter();

  const handleCardClick = () => {
    router.push(`/conversations/${id}`);
  };

  const handleExpandToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded((prev) => !prev);
  };

  return (
    <article
      onClick={handleCardClick}
      className={cn(
        "group cursor-pointer rounded-xl border border-slate-800 bg-slate-900/50 p-4",
        "transition-all hover:border-slate-700 hover:bg-slate-900/80"
      )}
    >
      {/* Header: Status badge + Title */}
      <div className="mb-3 flex flex-col gap-2">
        <div className="flex-shrink-0">{getIdeaStatusBadge(status)}</div>
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

      {/* Footer: Dates + Expand toggle */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3 text-[10px] uppercase tracking-wide text-slate-500">
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Created {formatRelativeTime(createdAt)}
          </span>
          <span>Updated {formatRelativeTime(updatedAt)}</span>
        </div>

        <button
          onClick={handleExpandToggle}
          type="button"
          className={cn(
            "inline-flex items-center gap-1 rounded px-2 py-1",
            "text-[10px] uppercase tracking-wide text-slate-400",
            "transition-colors hover:bg-slate-800 hover:text-slate-300"
          )}
        >
          Runs
          {isExpanded ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
        </button>
      </div>

      {/* Expandable Runs Section */}
      {isExpanded && <IdeationQueueRunsList conversationId={id} />}
    </article>
  );
}

export const IdeationQueueCard = memo(IdeationQueueCardComponent);
```

---

## 8. Pitfalls to Avoid

### 1. DO NOT Import `useRouter` from `next/router`

```typescript
// WRONG - Pages Router (deprecated)
import { useRouter } from "next/router";

// CORRECT - App Router (Next.js 15)
import { useRouter } from "next/navigation";
```

### 2. DO NOT Forget `stopPropagation` on Nested Clickables

```typescript
// WRONG - Both card and run navigation fire
<article onClick={handleCardClick}>
  <button onClick={handleRunClick}>...</button>
</article>

// CORRECT - Only run navigation fires
<article onClick={handleCardClick}>
  <button onClick={(e) => { e.stopPropagation(); handleRunClick(); }}>...</button>
</article>
```

### 3. DO NOT Add `'use client'` to Every File

```typescript
// WRONG - Unnecessary, creates boundary overhead
// IdeationQueueRunItem.tsx
'use client';  // Don't need this - parent is already client

// CORRECT - Let parent's boundary apply
// IdeationQueueRunItem.tsx
import { memo } from "react";
// ...
```

### 4. DO NOT Use `enabled: false` for Conditional Rendering

```typescript
// WRONG - Query exists but is disabled
const { data } = useQuery({
  queryKey: ["runs", id],
  queryFn: fetchRuns,
  enabled: isExpanded,  // Wastes query subscription
});

// CORRECT - Only mount component when needed
{isExpanded && <RunsList conversationId={id} />}
// Hook inside RunsList runs unconditionally when mounted
```

### 5. DO NOT Wrap `<Link>` with Click Handlers

```typescript
// WRONG - Interferes with Link behavior
<Link href="/research/123" onClick={(e) => { e.stopPropagation(); }}>
  View
</Link>

// CORRECT - Use button + router for complex click handling
<button onClick={(e) => { e.stopPropagation(); router.push("/research/123"); }}>
  View
</button>
```

### 6. DO NOT Forget Type Exports in `index.ts`

```typescript
// frontend/src/features/conversation/index.ts
// WRONG - Types missing
export { IdeationQueueCard } from "./components/IdeationQueueCard";

// CORRECT - Include types
export { IdeationQueueCard } from "./components/IdeationQueueCard";
export { IdeationQueueRunsList } from "./components/IdeationQueueRunsList";
export { IdeationQueueRunItem } from "./components/IdeationQueueRunItem";
export { useConversationResearchRuns } from "./hooks/useConversationResearchRuns";
export type {
  IdeationQueueRunItemProps,
  IdeationQueueRunsListProps,
} from "./types/ideation-queue.types";
```

### 7. DO NOT Use `cacheTime` in React Query v5

```typescript
// WRONG - v4 syntax
useQuery({
  queryKey: ["runs", id],
  queryFn: fetchRuns,
  cacheTime: 300000,  // Deprecated in v5
});

// CORRECT - v5 syntax
useQuery({
  queryKey: ["runs", id],
  queryFn: fetchRuns,
  gcTime: 300000,  // Renamed in v5
});
```

---

## 9. Documentation References

**Next.js 15 Official Documentation:**
- Getting Started: https://nextjs.org/docs/15/app/getting-started
- Server & Client Components: https://nextjs.org/docs/15/app/getting-started/server-and-client-components
- Linking & Navigation: https://nextjs.org/docs/15/app/getting-started/linking-and-navigating
- Caching & Revalidating: https://nextjs.org/docs/15/app/getting-started/caching-and-revalidating

**TanStack Query v5 Documentation:**
- Query Keys: https://tanstack.com/query/v5/docs/react/guides/query-keys
- Caching: https://tanstack.com/query/v5/docs/react/guides/caching

---

## 10. Summary for Executor

### Key Implementation Points

1. **`'use client'` Directive**
   - Only add to `useConversationResearchRuns.ts` hook
   - Other new components inherit client boundary from `IdeationQueueCard`

2. **React Query**
   - Use `gcTime` (not `cacheTime`) - renamed in v5
   - Query key: `["conversation-research-runs", conversationId]`
   - `staleTime: 30 * 1000` for run status freshness

3. **Navigation**
   - Use `useRouter` from `next/navigation` (NOT `next/router`)
   - Use `<button>` + `router.push()` for run items (not `<Link>`)
   - Always call `e.stopPropagation()` on nested clickables

4. **Component Structure**
   - Memoize all list item components with `React.memo()`
   - Conditional render runs list: `{isExpanded && <RunsList />}`
   - Remove outer `<Link>` from card, use `onClick` + `router.push()`

5. **Performance**
   - No dynamic imports needed (components are small)
   - No virtualization needed (limited to 5 runs)
   - Cache handles re-expansion instantly

---

## Approval Request

Please review this Next.js 15 technical guidance. Reply with:
- **"proceed"** or **"yes"** - Guidance is correct, continue to implementation
- **"modify: [your feedback]"** - I'll adjust the recommendations
- **"elaborate"** - Provide more details and context for review
- **"stop"** - Pause here

Waiting for your approval...
