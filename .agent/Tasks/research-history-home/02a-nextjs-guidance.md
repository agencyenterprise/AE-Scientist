# Next.js 15 Guidance: Research History Feature

## Agent
nextjs-expert

## Timestamp
2025-12-03 16:00

## Version Detection

| Package | Version | Notes |
|---------|---------|-------|
| next | 15.4.7 | App Router, Turbopack enabled for dev |
| react | 19.1.0 | Latest stable, supports `use()` hook |
| react-dom | 19.1.0 | |
| typescript | ^5 | |
| @tanstack/react-query | ^5.90.10 | Already configured with QueryProvider |
| zustand | ^5.0.8 | Available for client state |
| date-fns | ^4.1.0 | For date formatting |

### Router Type
**App Router** - Confirmed by presence of `/app` directory structure

### Key Configuration
- `next.config.ts` is minimal (only image remote patterns)
- Turbopack enabled in dev (`next dev --turbopack`)
- No experimental flags needed

---

## Recommendations

### 1. "use client" Directive

**Guidance**: Yes, the proposed components need `"use client"`, but the architecture is already optimized.

**Current Analysis**:
- The home page (`/app/(dashboard)/page.tsx`) is a **Server Component** (no `"use client"` directive)
- `CreateHypothesisForm` already uses `"use client"` and is imported into the server component
- This pattern should be replicated for `ResearchHistoryList`

**Best Practice**: Keep the boundary at `ResearchHistoryList` level, not at the individual sub-components. Since child components inherit the client boundary, the sub-components (`ResearchHistoryCard`, `ResearchHistoryEmpty`, `ResearchHistorySkeleton`) technically don't need the directive, but including it is harmless and makes intent explicit.

**Recommendation**:
- `ResearchHistoryList.tsx` - REQUIRED `"use client"` (uses hooks)
- `ResearchHistoryCard.tsx` - OPTIONAL but recommended for clarity (uses Next.js `Link`)
- `ResearchHistoryEmpty.tsx` - NOT REQUIRED (stateless, but include for consistency)
- `ResearchHistorySkeleton.tsx` - NOT REQUIRED (pure CSS animation)

**Note**: The architecture doc already correctly includes `"use client"` on all components. This is a safe approach and follows the project's existing patterns.

---

### 2. Data Fetching Pattern

**Recommendation**: Use TanStack React Query instead of raw `useState` + `useEffect`.

**Rationale**:
1. **Project already uses React Query** - `QueryProvider` is configured in `shared/providers/`
2. **Existing pattern** - `useModelSelectorData` demonstrates the project's React Query usage
3. **Benefits**: Automatic caching, background refetching, loading states, error handling
4. **Consistency** - Aligns with established project patterns

**Updated Hook Design**:

```typescript
// features/research/hooks/useRecentResearch.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";
import { convertApiResearchRunList } from "@/shared/lib/api-adapters";
import type { ResearchRun, ResearchRunListResponseApi } from "@/types/research";

async function fetchRecentResearch(): Promise<ResearchRun[]> {
  const data = await apiFetch<ResearchRunListResponseApi>("/research-runs/?limit=10");
  const converted = convertApiResearchRunList(data);
  return converted.items;
}

interface UseRecentResearchReturn {
  researchRuns: ResearchRun[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useRecentResearch(): UseRecentResearchReturn {
  const query = useQuery({
    queryKey: ["recent-research"],
    queryFn: fetchRecentResearch,
    staleTime: 30 * 1000, // 30 seconds - show fresh data often on home page
  });

  return {
    researchRuns: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error ? (query.error instanceof Error ? query.error.message : "Failed to fetch research history") : null,
    refetch: query.refetch,
  };
}
```

**Why NOT raw `useState` + `useEffect`**:
- The proposed architecture uses this pattern, but it misses:
  - Request deduplication (if component remounts)
  - Automatic background refetching
  - Caching across navigation
  - Standardized error handling with `ApiError`

**Why NOT React 19's `use()` hook**:
- The `use()` hook is designed for Server Component -> Client Component data passing
- It requires passing a Promise from a server component as a prop
- This would require restructuring the home page significantly
- React Query provides more features (caching, refetching, mutations)
- The project already has React Query set up and uses it

---

### 3. React 19 Considerations

**New Features Available**:
- `use()` hook - Not recommended for this feature (see above)
- React Compiler optimizations - Automatic, no changes needed
- Improved Suspense integration - Already leveraged via React Query

**No Changes Needed**: The proposed architecture is compatible with React 19. The `useState`, `useEffect`, `useCallback` patterns still work fine, but React Query is preferred for data fetching.

**Future Consideration**: If the home page were to be refactored to fetch data server-side, you could:
1. Fetch data in the server component
2. Pass the Promise to `ResearchHistoryList`
3. Use `use()` to unwrap it with Suspense fallback

This is NOT recommended for this feature because:
- Home page needs user authentication (handled by `apiFetch`)
- React Query caching is valuable for this frequently-visited page
- Keeps implementation consistent with existing patterns

---

### 4. Link Component

**No Breaking Changes in Next.js 15.4.7**.

**Best Practices**:
- No need for child `<a>` tag (removed requirement in v13)
- Default prefetch behavior is optimal
- Use `scroll={false}` if you want to maintain scroll position (not needed here)

**Current Usage in Architecture** - Already correct:
```tsx
<Link
  href={`/conversations/${research.conversationId}`}
  className="inline-flex items-center gap-1.5 ..."
>
  <RotateCcw className="h-3.5 w-3.5" />
  Relaunch
</Link>
```

**New Feature Available** (v15.3.0+): `onNavigate` for navigation control. Not needed for this simple link.

---

### 5. Error Handling

**Current Architecture Error Handling** - Good but can be improved:

The architecture shows inline error display in `ResearchHistoryList`:
```tsx
{error && !isLoading && (
  <div className="flex items-center gap-2 text-red-400">
    <AlertCircle className="h-4 w-4" />
    <span className="text-sm">{error}</span>
  </div>
)}
```

**Recommendation**: This is acceptable for a simple feature. For more robust error handling:

1. **React Query handles 401s globally** - The `QueryProvider` already redirects to `/login` on 401 errors
2. **API errors are typed** - `ApiError` class provides status codes
3. **No Error Boundary needed** - The inline approach is fine for non-critical UI

**Optional Enhancement** - Add retry button:
```tsx
{error && !isLoading && (
  <div className="flex flex-col items-center gap-2 py-4">
    <AlertCircle className="h-6 w-6 text-red-400" />
    <p className="text-sm text-red-400">{error}</p>
    <button
      onClick={() => refetch()}
      className="text-xs text-slate-400 hover:text-slate-300"
    >
      Try again
    </button>
  </div>
)}
```

---

## Code Patterns

### Recommended Hook Implementation (using React Query)

```typescript
// /frontend/src/features/research/hooks/useRecentResearch.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";
import { convertApiResearchRunList } from "@/shared/lib/api-adapters";
import type { ResearchRun, ResearchRunListResponseApi } from "@/types/research";

async function fetchRecentResearch(): Promise<ResearchRun[]> {
  const data = await apiFetch<ResearchRunListResponseApi>("/research-runs/?limit=10");
  const converted = convertApiResearchRunList(data);
  return converted.items;
}

export function useRecentResearch() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["recent-research"],
    queryFn: fetchRecentResearch,
    staleTime: 30 * 1000, // 30 seconds
  });

  return {
    researchRuns: data ?? [],
    isLoading,
    error: error instanceof Error ? error.message : error ? "Failed to fetch" : null,
    refetch,
  };
}
```

### Updated List Component (using hook with refetch)

```typescript
// /frontend/src/features/research/components/ResearchHistoryList.tsx
"use client";

import { useRecentResearch } from "../hooks/useRecentResearch";
import { ResearchHistoryCard } from "./ResearchHistoryCard";
import { ResearchHistoryEmpty } from "./ResearchHistoryEmpty";
import { ResearchHistorySkeleton } from "./ResearchHistorySkeleton";
import { AlertCircle, RefreshCw } from "lucide-react";

export function ResearchHistoryList() {
  const { researchRuns, isLoading, error, refetch } = useRecentResearch();

  return (
    <div className="w-full text-left">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-white">
          Your Recent Research
        </h2>
        {!isLoading && researchRuns.length > 0 && (
          <button
            onClick={() => refetch()}
            className="text-xs text-slate-500 hover:text-slate-400 flex items-center gap-1"
          >
            <RefreshCw className="h-3 w-3" />
            Refresh
          </button>
        )}
      </div>

      <div className="rounded-xl border border-slate-800/70 bg-slate-950/80 p-4">
        {isLoading && <ResearchHistorySkeleton />}

        {error && !isLoading && (
          <div className="flex flex-col items-center gap-2 py-4">
            <AlertCircle className="h-6 w-6 text-red-400" />
            <p className="text-sm text-red-400">{error}</p>
            <button
              onClick={() => refetch()}
              className="text-xs text-slate-400 hover:text-slate-300 underline"
            >
              Try again
            </button>
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

---

## Warnings

### Deprecated Patterns to Avoid

1. **Do NOT use `getServerSideProps` or `getStaticProps`** - These are Pages Router patterns, not App Router
2. **Do NOT wrap Link in `<a>` tag** - Not needed since Next.js 13
3. **Avoid `useEffect` for data fetching when React Query is available** - Use the established pattern

### Version-Specific Gotchas

1. **Next.js 15.x params change** - In page components, `params` and `searchParams` are now Promises. This doesn't affect this feature since we're using client-side data fetching.

2. **React Query v5 syntax** - The project uses v5, which has slightly different API:
   - `isLoading` vs `isPending` - Both work, `isLoading` is for initial load only
   - `refetch` returns a Promise - Don't need to await it for UI purposes

---

## Architecture Changes Recommended

### Change #1: Update `useRecentResearch` hook to use React Query

**Current (in 02-architecture.md)**: Uses `useState` + `useEffect` + `useCallback`

**Recommended**: Use `useQuery` from TanStack React Query

**Reason**: Consistency with project patterns, built-in caching, better error handling

### Change #2: Add optional refresh button to list component

**Current**: No manual refresh option

**Recommended**: Add small refresh button in header (see code pattern above)

**Reason**: Users may want to see updated status for running experiments

### No Other Changes Needed

The rest of the architecture is sound:
- Component structure is appropriate
- Utility extraction plan is correct
- File locations follow project conventions
- UI implementation matches existing patterns

---

## Documentation References

- [Next.js 15 Client Components](https://nextjs.org/docs/app/building-your-application/rendering/client-components)
- [Next.js 15 Data Fetching](https://nextjs.org/docs/app/building-your-application/data-fetching)
- [Next.js 15 Link Component](https://nextjs.org/docs/app/api-reference/components/link)
- [React 19 use() Hook](https://react.dev/reference/react/use)
- [TanStack React Query v5](https://tanstack.com/query/latest)

---

## Summary for Executor

### Key Points to Follow

1. **Use React Query for the hook** - Replace the `useState`/`useEffect` pattern with `useQuery`. This aligns with the existing `useModelSelectorData` pattern.

2. **Keep `"use client"` on all new components** - This is already in the architecture and is correct. The boundary at `ResearchHistoryList` is sufficient, but including it on child components is fine.

3. **No changes to Link component usage** - The architecture's Link implementation is correct for Next.js 15.

4. **Error handling is adequate** - The inline error display is fine. Optionally add a retry button.

5. **Follow the implementation order** - Extract utilities first, then hook, then components. This is already specified in the architecture.

### Critical Implementation Notes

1. Import `useQuery` from `@tanstack/react-query`
2. Use the `queryKey: ["recent-research"]` for cache identification
3. Set `staleTime: 30 * 1000` for reasonable freshness
4. The `QueryProvider` is already in the app layout - no setup needed

### Testing Checklist
- [ ] Loading skeleton appears on initial load
- [ ] Data displays after fetch completes
- [ ] Empty state shows when no research runs exist
- [ ] Error state shows on API failure (can test by disconnecting network)
- [ ] Clicking "Relaunch" navigates to correct conversation
- [ ] Research board page (`/research`) still works after utility extraction
