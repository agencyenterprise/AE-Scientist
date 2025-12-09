# Reusable Assets Analysis - Inline Conversation View

## Agent
codebase-analyzer

## Timestamp
2025-12-08

## Scan Summary

- Features analyzed: `conversation`, `project-draft`, `dashboard`
- Shared utilities found: 4
- Reusable hooks found: 2
- UI components found: 8

---

## MUST REUSE

These assets exactly match our needs - import and use directly without modification.

### 1. ProjectDraftContent (Core Display Component)

| Property | Value |
|----------|-------|
| **Path** | `/frontend/src/features/project-draft/components/ProjectDraftContent.tsx` |
| **What it does** | Renders all idea sections (Hypothesis, Related Work, Abstract, Experiments, Expected Outcome, Risk Factors) with edit buttons and modal handling |
| **Import** | `import { ProjectDraftContent } from "@/features/project-draft/components/ProjectDraftContent"` |
| **Why relevant** | This is THE component we need for inline view - already renders all sections with proper formatting |

**Props interface:**
```typescript
interface ProjectDraftContentProps {
  projectDraft: Idea;
  conversationId: string;
  onUpdate: (updatedIdea: Idea) => void;
  sectionDiffs?: SectionDiffs | null;
}
```

**Key insight**: The `onEdit` callbacks in sections are passed as props. If we pass `onUpdate={() => {}}` (no-op), the modals never get opened because state never changes. Combined with CSS `pointer-events-none` on buttons, this makes a clean read-only mode.

---

### 2. ProjectDraftSkeleton (Loading State)

| Property | Value |
|----------|-------|
| **Path** | `/frontend/src/features/project-draft/components/ProjectDraftSkeleton.tsx` |
| **What it does** | Animated skeleton loader for idea content |
| **Import** | `import { ProjectDraftSkeleton } from "@/features/project-draft/components/ProjectDraftSkeleton"` |
| **Why relevant** | Consistent loading state while fetching idea data |

**Current implementation:**
```tsx
export function ProjectDraftSkeleton() {
  return (
    <div className="space-y-4">
      <div className="animate-pulse space-y-2">
        <div className="h-3 bg-primary/30 rounded w-full"></div>
        <div className="h-3 bg-primary/30 rounded w-5/6"></div>
        <div className="h-3 bg-primary/30 rounded w-4/5"></div>
        <div className="h-3 bg-primary/30 rounded w-3/4"></div>
      </div>
    </div>
  );
}
```

---

### 3. PageCard (Container Component)

| Property | Value |
|----------|-------|
| **Path** | `/frontend/src/shared/components/PageCard.tsx` |
| **What it does** | Styled container with gradient effects and rounded borders |
| **Import** | `import { PageCard } from "@/shared/components/PageCard"` |
| **Why relevant** | Already used in conversations page for the second card (currently empty) |

---

### 4. apiFetch (API Client)

| Property | Value |
|----------|-------|
| **Path** | `/frontend/src/shared/lib/api-client.ts` |
| **What it does** | Type-safe fetch wrapper with auth, error handling |
| **Import** | `import { apiFetch } from "@/shared/lib/api-client"` |
| **Why relevant** | Needed for fetching idea data in new hook |

**Existing usage for ideas:**
```typescript
const data = await apiFetch<IdeaGetResponse>(`/conversations/${id}/idea`);
```

---

### 5. cn Utility (Class Merging)

| Property | Value |
|----------|-------|
| **Path** | `/frontend/src/shared/lib/utils.ts` |
| **What it does** | Combines Tailwind classes with clsx + tailwind-merge |
| **Import** | `import { cn } from "@/shared/lib/utils"` |
| **Why relevant** | For conditional selection styling on cards |

**Example:**
```tsx
className={cn(
  "base-classes",
  isSelected && "ring-2 ring-sky-500"
)}
```

---

### 6. IdeationQueueEmpty (Empty State Pattern)

| Property | Value |
|----------|-------|
| **Path** | `/frontend/src/features/conversation/components/IdeationQueueEmpty.tsx` |
| **What it does** | Centered empty state with icon and message |
| **Import** | `import { IdeationQueueEmpty } from "@/features/conversation"` |
| **Why relevant** | Reference pattern for our inline view empty state |

**Pattern to follow:**
```tsx
<div className="flex h-64 items-center justify-center">
  <div className="text-center">
    <Icon className="mx-auto mb-3 h-10 w-10 text-slate-600" />
    <h3 className="text-lg font-medium text-slate-300">Title</h3>
    <p className="mt-1 text-sm text-slate-500">Description</p>
  </div>
</div>
```

---

### 7. Eye Icon (Lucide)

| Property | Value |
|----------|-------|
| **Path** | lucide-react (already installed) |
| **What it does** | View/preview icon |
| **Import** | `import { Eye } from "lucide-react"` |
| **Why relevant** | Used for empty state and "View Mode" badge |

Already used in:
- `ConversationsBoardTable.tsx` - "View Conversation" button
- `research-board-card-footer.tsx` - View action

---

### 8. Types: Idea, IdeaGetResponse

| Property | Value |
|----------|-------|
| **Path** | `/frontend/src/types/index.ts` |
| **What it does** | TypeScript types for idea data |
| **Import** | `import type { Idea, IdeaGetResponse } from "@/types"` |
| **Why relevant** | Type safety for fetched idea data |

---

## CONSIDER REUSING

These assets could be adapted with minor modifications or used as reference patterns.

### 1. useConversationResearchRuns (Data Fetching Pattern)

| Property | Value |
|----------|-------|
| **Path** | `/frontend/src/features/conversation/hooks/useConversationResearchRuns.ts` |
| **What it does** | Fetches research runs for a conversation using React Query |
| **Import** | `import { useConversationResearchRuns } from "@/features/conversation"` |
| **Why relevant** | **Excellent pattern** for our `useSelectedIdeaData` hook |

**Pattern to follow:**
```typescript
export function useConversationResearchRuns(conversationId: number) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["conversation-research-runs", conversationId],
    queryFn: () => fetchData(conversationId),
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  });

  return {
    runs: data ?? [],
    isLoading,
    error: error instanceof Error ? error.message : error ? "Error message" : null,
    refetch,
  };
}
```

**Adaptation needed:**
- Change to fetch `/conversations/${id}/idea` endpoint
- Handle `conversationId: number | null` for when no selection
- Return `idea: Idea | null` instead of `runs[]`

---

### 2. useProjectDraftData (Alternative Pattern)

| Property | Value |
|----------|-------|
| **Path** | `/frontend/src/features/project-draft/hooks/use-project-draft-data.ts` |
| **What it does** | Fetches and manages idea data with polling |
| **Import** | Direct hook reference |
| **Why relevant** | Shows the API call pattern and response handling |

**Key insights:**
- Uses `useState` + `useEffect` instead of React Query
- Has polling for generation status
- Returns `projectDraft`, `isLoading`, `setProjectDraft`, `updateProjectDraft`

**Recommendation:** Use React Query pattern from `useConversationResearchRuns` instead - simpler, better caching for our use case (no polling needed for read-only view).

---

### 3. StringSection (Edit Button Pattern)

| Property | Value |
|----------|-------|
| **Path** | `/frontend/src/features/project-draft/components/StringSection.tsx` |
| **What it does** | Renders a section with title, content, and optional edit button |
| **Why relevant** | Shows how edit buttons are rendered - they only appear if `onEdit` is provided |

**Key insight for read-only mode:**
```tsx
// In StringSection.tsx, edit button only renders if onEdit exists:
{onEdit && (
  <button onClick={onEdit} className="...">
    <Pencil className="w-3.5 h-3.5" />
  </button>
)}
```

If we wanted surgical control, we could pass `undefined` for all `onEdit` props. However, `ProjectDraftContent` handles the edit hooks internally, so the CSS `pointer-events-none` approach is simpler.

---

### 4. Ring Selection Styling Pattern

| Property | Value |
|----------|-------|
| **Usage examples** | Multiple components in codebase |
| **Pattern** | `focus:ring-2 focus:ring-sky-500` |
| **Why relevant** | Consistent selection highlight styling |

**Existing pattern from inputs:**
```tsx
className="... focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/50 ..."
```

**Proposed for card selection:**
```tsx
className={cn(
  "group cursor-pointer rounded-xl border border-slate-800 bg-slate-900/50 p-4",
  "transition-all hover:border-slate-700 hover:bg-slate-900/80",
  isSelected && "ring-2 ring-sky-500 border-sky-500/50 bg-slate-900/80"
)}
```

---

## CREATE NEW

These need to be built from scratch because nothing suitable exists.

### 1. InlineIdeaView Component

| Property | Value |
|----------|-------|
| **Proposed path** | `/frontend/src/features/conversation/components/InlineIdeaView.tsx` |
| **Why new** | Specific wrapper combining ProjectDraftContent with read-only mode, empty state, loading state, and View Mode indicator |

**What it must do:**
1. Accept `conversationId: number | null`
2. Show empty state when `conversationId === null`
3. Show loading skeleton while fetching
4. Show error state if fetch fails
5. Wrap ProjectDraftContent with:
   - "View Mode" badge
   - CSS `pointer-events-none` on edit buttons
   - No-op `onUpdate` handler

**Proposed structure:**
```tsx
export function InlineIdeaView({ conversationId }: { conversationId: number | null }) {
  const { idea, isLoading, error } = useSelectedIdeaData(conversationId);

  if (!conversationId) return <InlineIdeaEmptyState />;
  if (isLoading) return <ProjectDraftSkeleton />;
  if (error) return <InlineIdeaError error={error} />;
  if (!idea) return <InlineIdeaEmptyState />;

  return (
    <div className="relative">
      <ViewModeBadge />
      <div className="[&_button]:pointer-events-none [&_button]:opacity-50">
        <ProjectDraftContent
          projectDraft={idea}
          conversationId={conversationId.toString()}
          onUpdate={() => {}}
        />
      </div>
    </div>
  );
}
```

---

### 2. useSelectedIdeaData Hook

| Property | Value |
|----------|-------|
| **Proposed path** | `/frontend/src/features/conversation/hooks/useSelectedIdeaData.ts` |
| **Why new** | Specific hook for fetching idea data based on selection state |

**What it must do:**
1. Accept `conversationId: number | null`
2. Skip query when `conversationId === null`
3. Fetch from `/conversations/${id}/idea`
4. Return `{ idea, isLoading, error }`

**Proposed implementation (following useConversationResearchRuns pattern):**
```typescript
export function useSelectedIdeaData(conversationId: number | null) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["selected-idea", conversationId],
    queryFn: () => apiFetch<IdeaGetResponse>(`/conversations/${conversationId}/idea`),
    enabled: conversationId !== null,
    staleTime: 60 * 1000, // 1 minute
    gcTime: 5 * 60 * 1000, // 5 minutes
  });

  return {
    idea: data?.idea ?? null,
    isLoading: conversationId !== null && isLoading,
    error: error instanceof Error ? error.message : null,
  };
}
```

---

### 3. Selection Props for IdeationQueueCard/List

| Property | Value |
|----------|-------|
| **Files to modify** | `ideation-queue.types.ts`, `IdeationQueueCard.tsx`, `IdeationQueueList.tsx` |
| **Why new** | No existing selection state pattern for these components |

**New types needed:**
```typescript
// Add to IdeationQueueCardProps
export interface IdeationQueueCardProps {
  // ... existing props
  selectedId?: number | null;
  onSelect?: (id: number) => void;
}

// Add to IdeationQueueListProps
export interface IdeationQueueListProps {
  // ... existing props
  selectedId?: number | null;
  onSelect?: (id: number) => void;
}
```

---

## Summary Table

| Category | Count | Items |
|----------|-------|-------|
| **MUST REUSE** | 8 | ProjectDraftContent, ProjectDraftSkeleton, PageCard, apiFetch, cn, IdeationQueueEmpty pattern, Eye icon, Types |
| **CONSIDER REUSING** | 4 | useConversationResearchRuns pattern, useProjectDraftData reference, StringSection pattern, Ring styling pattern |
| **CREATE NEW** | 3 | InlineIdeaView, useSelectedIdeaData, Selection props |

---

## File Exports to Update

After implementation, update these barrel exports:

### /frontend/src/features/conversation/index.ts
```typescript
// Add new exports
export { InlineIdeaView } from "./components/InlineIdeaView";
export { useSelectedIdeaData } from "./hooks/useSelectedIdeaData";
```

---

## Key Implementation Notes

### Read-Only Mode Strategy

The PRD proposes CSS `pointer-events-none` approach. After analyzing `StringSection.tsx`, I confirm this is the cleanest approach because:

1. **Edit buttons only render if `onEdit` is provided** - but `ProjectDraftContent` internally creates these handlers via `useSectionEdit` hook
2. **CSS approach is non-invasive** - no changes to existing components
3. **Visual indicator needed** - buttons should appear disabled (opacity-50)

**Recommended CSS wrapper:**
```tsx
<div className="[&_button]:pointer-events-none [&_button]:opacity-50">
  <ProjectDraftContent ... />
</div>
```

This targets all buttons within the content, making them visually disabled and non-interactive.

### Selection State Pattern

Current `IdeationQueueCard` has:
```tsx
const handleCardClick = () => {
  router.push(`/conversations/${id}`);
};
```

Change to:
```tsx
const handleCardClick = () => {
  if (onSelect) {
    onSelect(id);
  } else {
    router.push(`/conversations/${id}`);
  }
};
```

This maintains backward compatibility - if no `onSelect` provided, defaults to navigation.

---

## Next Steps

1. **Architecture phase** should define:
   - Exact component interfaces
   - State flow diagram
   - Error handling strategy

2. **Implementation phase** should follow order:
   - Phase 1: Types + selection props
   - Phase 2: useSelectedIdeaData hook
   - Phase 3: InlineIdeaView component
   - Phase 4: Integration in page.tsx
