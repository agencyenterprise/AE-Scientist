# Next.js 15 Technical Guidance

## Agent
nextjs-15-expert

## Timestamp
2025-12-08

## Project Analysis

### Detected Versions
| Package | Version | Notes |
|---------|---------|-------|
| next | 15.4.8 | App Router, Turbopack dev |
| react | 19.1.2 | React 19 with `use` hook support |
| typescript | ^5 | TypeScript 5.x |
| @tanstack/react-query | ^5.90.10 | React Query v5 for client data fetching |
| zustand | ^5.0.8 | Global state management (available) |

### Router Type
**App Router** (confirmed from `app/(dashboard)/conversations/page.tsx` structure)

### Key Configuration
- Turbopack enabled for development (`next dev --turbopack`)
- Image remote patterns configured for localhost:8000 and railway.app
- TypeScript strict mode (standard Next.js 15 setup)

---

## Version-Specific Guidance

### Confirmed Next.js 15.x Patterns in Use

The codebase already follows Next.js 15 best practices:

1. **`'use client'` correctly placed** - Only in components that need interactivity
2. **React Query v5** - Used for client-side data fetching (e.g., `useConversationResearchRuns`)
3. **App Router structure** - `app/(dashboard)/` route groups
4. **Path aliases** - `@/` imports configured

---

## Component Directive Strategy

### Where to Place `'use client'`

| Component | Needs `'use client'`? | Reason |
|-----------|----------------------|--------|
| `conversations/page.tsx` | **YES** (already has it) | Uses `useState` for selection state |
| `IdeationQueueCard.tsx` | **YES** (already has it) | Uses `useState`, `useRouter`, event handlers |
| `IdeationQueueList.tsx` | **NO** | Pure render, receives callbacks as props |
| `InlineIdeaView.tsx` | **YES** (needs it) | Uses custom hook `useSelectedIdeaData` with React Query |
| `useSelectedIdeaData.ts` | **YES** (needs it) | Hook file using `useQuery` from React Query |

### Key Principle
> "Mark only specific interactive components with `'use client'`, not entire sections. This reduces bundle size."
> -- Next.js 15 Official Documentation

**Current codebase correctly follows this** - components like `IdeationQueueList.tsx` don't have `'use client'` because they don't use hooks or event handlers directly.

### Directive Placement for New Files

```typescript
// /features/conversation/components/InlineIdeaView.tsx
'use client';

import { useSelectedIdeaData } from '../hooks/useSelectedIdeaData';
// ... rest of imports and component
```

```typescript
// /features/conversation/hooks/useSelectedIdeaData.ts
'use client';

import { useQuery } from '@tanstack/react-query';
// ... rest of hook implementation
```

---

## Data Fetching Patterns

### React Query v5 Integration with Next.js 15

The project uses React Query v5 for client-side data fetching. This is the **correct pattern** for this feature because:

1. **Selection-based fetching** - Data fetched reactively when `selectedId` changes
2. **Caching** - Previous selections are cached and instantly available
3. **Background refetching** - Stale data updated in background

### Query Key Structure

Follow the existing pattern from `useConversationResearchRuns`:

```typescript
// Existing pattern in codebase
queryKey: ["conversation-research-runs", conversationId]

// New hook should follow same pattern
queryKey: ["selected-idea", conversationId]
```

**Why this structure:**
- Array-based keys enable automatic invalidation
- Including `conversationId` ensures unique cache entries per conversation
- React Query v5 handles enabled/disabled states when `conversationId` is null

### Caching Strategy

```typescript
export function useSelectedIdeaData(conversationId: number | null) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["selected-idea", conversationId],
    queryFn: async () => {
      const response = await apiFetch<IdeaGetResponse>(
        `/conversations/${conversationId}/idea`
      );
      return response.idea;
    },
    // IMPORTANT: Disable query when no selection
    enabled: conversationId !== null,
    // Cache settings optimized for read-only preview
    staleTime: 60 * 1000,  // 1 minute - idea content is relatively stable
    gcTime: 5 * 60 * 1000, // 5 minutes - keep in cache for re-selections
  });

  return {
    idea: data ?? null,
    isLoading: conversationId !== null && isLoading,
    error: error instanceof Error ? error.message : null,
  };
}
```

### Cache Behavior Explanation

| Action | Cache Behavior |
|--------|----------------|
| Select conversation A | Fetch and cache under `["selected-idea", A]` |
| Select conversation B | Fetch and cache under `["selected-idea", B]` |
| Re-select conversation A | **Cache hit** if within `staleTime` (instant display) |
| After `staleTime` | Show cached data + background refetch |
| After `gcTime` | Cache entry removed, fresh fetch on next selection |

---

## State Management Guidelines

### Local useState is Correct

For this feature, local `useState` in the page component is the **correct choice**:

```typescript
// In conversations/page.tsx
const [selectedId, setSelectedId] = useState<number | null>(null);
```

**Why NOT use Zustand or Context:**
1. State is page-local (only conversations page needs it)
2. No other routes consume this state
3. Selection doesn't persist across navigation (intentional)
4. Simpler mental model and fewer dependencies

### State Flow Pattern

```
User clicks card
       |
       v
IdeationQueueCard calls onSelect(id)
       |
       v
Page component setSelectedId(id)
       |
       +---> IdeationQueueList receives selectedId (for styling)
       |
       +---> InlineIdeaView receives conversationId (triggers fetch)
```

### Avoiding Unnecessary Re-renders

The current architecture is already optimized:

1. **IdeationQueueCard is memoized** - `memo(IdeationQueueCardComponent)`
2. **Selection state is minimal** - Only `number | null`, not complex objects
3. **React Query handles data** - Component doesn't re-render on every fetch

**Additional optimization for new props:**

```typescript
// In IdeationQueueCard - compare by value, not reference
export const IdeationQueueCard = memo(IdeationQueueCardComponent, (prev, next) => {
  return (
    prev.id === next.id &&
    prev.title === next.title &&
    prev.abstract === next.abstract &&
    prev.status === next.status &&
    prev.createdAt === next.createdAt &&
    prev.updatedAt === next.updatedAt &&
    prev.isSelected === next.isSelected
    // Note: onSelect callback comparison intentionally omitted (reference stable from parent)
  );
});
```

---

## Performance Guidelines

### Memoization Strategies

#### React.memo Usage

Already in place for `IdeationQueueCard`. No changes needed for the memo wrapper itself.

#### useCallback for Stable Callbacks

In `conversations/page.tsx`, the `setSelectedId` from `useState` is already stable. However, if you create wrapper functions:

```typescript
// AVOID - creates new function reference on every render
<IdeationQueueList
  onSelect={(id) => setSelectedId(id)}  // BAD
/>

// CORRECT - direct reference is stable
<IdeationQueueList
  onSelect={setSelectedId}  // GOOD - setSelectedId is stable
/>
```

#### When NOT to Memoize

- `InlineIdeaView` - Single instance, no list rendering
- Simple display components - Memoization overhead exceeds benefit

### Code Splitting Considerations

For this feature, code splitting is **not needed** because:
1. `ProjectDraftContent` is already part of the main bundle (used in detail page)
2. `InlineIdeaView` is small and always rendered in this page
3. No heavy libraries being added

**If future optimization needed:**
```typescript
// Only if InlineIdeaView becomes heavy
const InlineIdeaView = dynamic(
  () => import('@/features/conversation/components/InlineIdeaView'),
  { loading: () => <ProjectDraftSkeleton /> }
);
```

---

## TypeScript with Next.js 15

### Import Path Conventions

Follow existing codebase patterns:

```typescript
// CORRECT - use path aliases
import { useSelectedIdeaData } from "@/features/conversation/hooks/useSelectedIdeaData";
import type { Idea, IdeaGetResponse } from "@/types";
import { cn } from "@/shared/lib/utils";

// AVOID - relative paths for cross-feature imports
import { someUtil } from "../../../shared/lib/utils";  // BAD
```

### Type Safety for Props

```typescript
// Strong typing for component props
interface InlineIdeaViewProps {
  conversationId: number | null;  // Explicit null for no selection
}

// Strong typing for hook return
interface UseSelectedIdeaDataReturn {
  idea: Idea | null;
  isLoading: boolean;
  error: string | null;
}
```

### Props Typing Best Practices

Follow existing patterns in codebase:

```typescript
// In ideation-queue.types.ts - extend existing interfaces
export interface IdeationQueueCardProps {
  id: number;
  title: string;
  abstract: string | null;
  status: IdeaStatus;
  createdAt: string;
  updatedAt: string;
  // NEW: Selection props (optional for backward compatibility)
  isSelected?: boolean;
  onSelect?: (id: number) => void;
}
```

**Key pattern:** Use `?` for optional props to maintain backward compatibility.

---

## App Router Patterns

### Client-Side State in App Router Pages

The `conversations/page.tsx` uses `'use client'` which is correct because:
1. It uses `useDashboard()` context
2. It uses `useConversationsFilter()` hook
3. It will use `useState` for selection

**This is the recommended pattern when a page needs interactivity.**

### Data Fetching Patterns

This feature uses a **hybrid approach**:

| Data | Fetching Method | Location |
|------|-----------------|----------|
| Conversations list | Server-side via context | `DashboardContext` (already set up) |
| Selected idea data | Client-side via React Query | `useSelectedIdeaData` hook |

**Why client-side for selected idea:**
1. Fetched on-demand based on user interaction
2. Needs caching across selection changes
3. React Query handles loading/error states elegantly

### Layout vs Page Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `layout.tsx` | Shared UI (sidebar, header), providers |
| `page.tsx` | Page-specific state, data composition, rendering |

**Selection state belongs in page.tsx** - it's page-specific and doesn't need to persist across routes.

---

## Code Examples

### Complete useSelectedIdeaData Hook

```typescript
// /frontend/src/features/conversation/hooks/useSelectedIdeaData.ts
'use client';

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";
import type { Idea, IdeaGetResponse } from "@/types";

export interface UseSelectedIdeaDataReturn {
  idea: Idea | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Fetches idea data for a selected conversation.
 * Returns null when no conversation is selected (conversationId is null).
 * Uses React Query for caching and automatic background refetching.
 */
export function useSelectedIdeaData(
  conversationId: number | null
): UseSelectedIdeaDataReturn {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["selected-idea", conversationId],
    queryFn: async () => {
      const response = await apiFetch<IdeaGetResponse>(
        `/conversations/${conversationId}/idea`
      );
      return response.idea;
    },
    enabled: conversationId !== null,
    staleTime: 60 * 1000,  // 1 minute
    gcTime: 5 * 60 * 1000, // 5 minutes
  });

  return {
    idea: data ?? null,
    // Only show loading when we have a selection and are actually loading
    isLoading: conversationId !== null && isLoading,
    error: error instanceof Error
      ? error.message
      : error
        ? "Couldn't load idea. Please try again."
        : null,
    refetch,
  };
}
```

### InlineIdeaView Component Structure

```typescript
// /frontend/src/features/conversation/components/InlineIdeaView.tsx
'use client';

import { Eye } from "lucide-react";
import { ProjectDraftContent } from "@/features/project-draft/components/ProjectDraftContent";
import { ProjectDraftSkeleton } from "@/features/project-draft/components/ProjectDraftSkeleton";
import { useSelectedIdeaData } from "../hooks/useSelectedIdeaData";

interface InlineIdeaViewProps {
  conversationId: number | null;
}

export function InlineIdeaView({ conversationId }: InlineIdeaViewProps) {
  const { idea, isLoading, error, refetch } = useSelectedIdeaData(conversationId);

  // Empty state - no selection
  if (conversationId === null) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Eye className="h-12 w-12 text-slate-600 mb-4" />
        <h3 className="text-sm font-medium text-slate-300 mb-1">
          Select an idea
        </h3>
        <p className="text-xs text-slate-500">
          Click on an idea above to preview its details
        </p>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return <ProjectDraftSkeleton />;
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="rounded-lg bg-red-500/10 p-4 text-red-400">
          <p className="text-sm">{error}</p>
          <button
            onClick={() => refetch()}
            className="mt-2 text-xs underline hover:no-underline"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  // No idea data for this conversation
  if (!idea) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Eye className="h-12 w-12 text-slate-600 mb-4" />
        <h3 className="text-sm font-medium text-slate-300 mb-1">
          No idea yet
        </h3>
        <p className="text-xs text-slate-500">
          This conversation doesn't have an idea generated yet
        </p>
      </div>
    );
  }

  // Success state - display read-only content
  return (
    <div className="relative">
      {/* View Mode indicator */}
      <div className="mb-4 flex items-center gap-2">
        <Eye className="h-4 w-4 text-slate-400" />
        <span className="text-xs uppercase tracking-wide text-slate-400">
          View Mode
        </span>
      </div>

      {/* Content with disabled edit interactions */}
      <div className="[&_button]:pointer-events-none [&_button]:opacity-50">
        <ProjectDraftContent
          projectDraft={idea}
          conversationId={conversationId.toString()}
          onUpdate={() => {}} // No-op handler for read-only mode
        />
      </div>
    </div>
  );
}
```

### Selection Styling Pattern

```typescript
// In IdeationQueueCard.tsx
className={cn(
  "group cursor-pointer rounded-xl border border-slate-800 bg-slate-900/50 p-4",
  "transition-all hover:border-slate-700 hover:bg-slate-900/80",
  // Selection styling - appears above hover state in specificity
  isSelected && "ring-2 ring-sky-500 border-sky-500/50 bg-slate-900/80"
)}
```

---

## Pitfalls to Avoid

### 1. Forgetting `enabled` in useQuery

```typescript
// BAD - will try to fetch with null ID
useQuery({
  queryKey: ["selected-idea", conversationId],
  queryFn: () => apiFetch(`/conversations/${conversationId}/idea`), // crashes
});

// GOOD - skip query when no selection
useQuery({
  queryKey: ["selected-idea", conversationId],
  queryFn: () => apiFetch(`/conversations/${conversationId}/idea`),
  enabled: conversationId !== null,  // REQUIRED
});
```

### 2. Creating New Callback References

```typescript
// BAD - new function created on every render, breaks memoization
<IdeationQueueCard
  onSelect={(id) => handleSelect(id)}  // New reference each render
/>

// GOOD - stable reference
<IdeationQueueCard
  onSelect={handleSelect}  // Same reference
/>
```

### 3. Overusing `'use client'`

```typescript
// BAD - entire component tree becomes client
// app/(dashboard)/conversations/page.tsx
'use client';

// Contains IdeationQueueList which doesn't need client rendering

// GOOD - current architecture
// IdeationQueueList doesn't have 'use client' (correct)
// IdeationQueueCard has 'use client' (needed for hooks)
```

### 4. Incorrect Loading State Logic

```typescript
// BAD - shows loading even when no selection
isLoading: isLoading,

// GOOD - only show loading when actually fetching
isLoading: conversationId !== null && isLoading,
```

### 5. Missing Type Imports

```typescript
// BAD - runtime import of types
import { Idea } from "@/types";

// GOOD - type-only import (removed at build time)
import type { Idea } from "@/types";
```

---

## Documentation References

**Next.js 15 Official Documentation:**
- Getting Started: https://nextjs.org/docs/15/app/getting-started
- Server & Client Components: https://nextjs.org/docs/15/app/getting-started/server-and-client-components
- Data Fetching: https://nextjs.org/docs/15/app/getting-started/fetching-data
- Caching & Revalidating: https://nextjs.org/docs/15/app/getting-started/caching-and-revalidating
- Routing: https://nextjs.org/docs/15/app/getting-started/layouts-and-pages

**React Query v5 Documentation:**
- Quick Start: https://tanstack.com/query/v5/docs/react/quick-start
- useQuery: https://tanstack.com/query/v5/docs/react/reference/useQuery

---

## Summary for Executor

### Key Points to Follow

1. **Add `'use client'`** to:
   - `InlineIdeaView.tsx` (new file)
   - `useSelectedIdeaData.ts` (new file)

2. **Do NOT add `'use client'`** to:
   - `IdeationQueueList.tsx` (doesn't need it)
   - Type files (they're types only)

3. **Use `enabled: conversationId !== null`** in useQuery to prevent fetching with null ID

4. **Pass `setSelectedId` directly** to `onSelect` prop (not wrapped in arrow function)

5. **Follow existing patterns** for:
   - React Query hook structure (see `useConversationResearchRuns`)
   - Error handling format
   - Type definitions in `ideation-queue.types.ts`
   - Class merging with `cn()` utility

6. **Read-only mode** uses CSS `[&_button]:pointer-events-none [&_button]:opacity-50`

---

## Approval Status

- [ ] Pending approval
- [ ] Approved - proceed to Implementation
- [ ] Modified - see feedback below

### Feedback (if modified)
{User feedback will be added here}

---

## APPROVAL REQUIRED

Please review the Next.js 15 technical guidance above. Reply with:
- **"proceed"** or **"yes"** - Guidance is correct, continue to implementation
- **"modify: [your feedback]"** - I'll adjust the recommendations
- **"elaborate"** - Provide more details and context for review
- **"stop"** - Pause here

Waiting for your approval...
