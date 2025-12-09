# Architecture Design - Inline Conversation View

## Agent
feature-architecture-expert

## Timestamp
2025-12-08

## Input Received
- Context: `00-context.md`, `01-planning.md`, `01a-reusable-assets.md`, `PRD.md`
- Codebase analysis: Existing components, hooks, types examined

---

## 1. Component Hierarchy Diagram

```
app/(dashboard)/conversations/page.tsx
|
+-- useState<number | null>(selectedId)
|
+-- PageCard (Main Card - Ideation Queue List)
|   |
|   +-- IdeationQueueHeader
|   |
|   +-- IdeationQueueList
|       |   props: conversations, emptyMessage, selectedId, onSelect
|       |
|       +-- IdeationQueueCard (for each conversation)
|               props: id, title, abstract, status, createdAt, updatedAt,
|                      isSelected, onSelect
|               |
|               +-- IdeationQueueRunsList (existing, unchanged)
|
+-- PageCard (Inline Idea View)
    |
    +-- InlineIdeaView
            props: conversationId
            |
            +-- [if null] InlineIdeaEmptyState
            |
            +-- [if loading] ProjectDraftSkeleton
            |
            +-- [if error] InlineIdeaError
            |
            +-- [if data] ReadOnlyWrapper
                    |
                    +-- ViewModeBadge
                    |
                    +-- ProjectDraftContent (existing, reused)
```

---

## 2. File Structure

### Files to CREATE

| File Path | Purpose |
|-----------|---------|
| `frontend/src/features/conversation/components/InlineIdeaView.tsx` | Main wrapper component for inline read-only idea display |
| `frontend/src/features/conversation/hooks/useSelectedIdeaData.ts` | React Query hook for fetching idea data on selection |

### Files to MODIFY

| File Path | Changes |
|-----------|---------|
| `frontend/src/features/conversation/types/ideation-queue.types.ts` | Add selection-related props interfaces |
| `frontend/src/features/conversation/components/IdeationQueueCard.tsx` | Add isSelected + onSelect props, selection styling |
| `frontend/src/features/conversation/components/IdeationQueueList.tsx` | Pass selectedId + onSelect to cards |
| `frontend/src/features/conversation/index.ts` | Export new component and hook |
| `frontend/src/app/(dashboard)/conversations/page.tsx` | Add selection state, render InlineIdeaView |

---

## 3. Component Specifications

### 3.1 InlineIdeaView (NEW)

**Purpose**: Wrapper component that orchestrates the inline idea display with empty, loading, error, and read-only content states.

**Responsibility (SRP)**: Single responsibility - coordinate the display of idea content based on selection state. Does NOT manage selection itself (that's the page's job).

**Props Interface**:
```typescript
interface InlineIdeaViewProps {
  conversationId: number | null;
}
```

**State Management**: No internal state. Uses `useSelectedIdeaData` hook for data fetching.

**Dependencies**:
```typescript
// MUST REUSE - exact imports
import { ProjectDraftContent } from "@/features/project-draft/components/ProjectDraftContent";
import { ProjectDraftSkeleton } from "@/features/project-draft/components/ProjectDraftSkeleton";
import { Eye } from "lucide-react";
import type { Idea } from "@/types";

// CREATE NEW - internal hook
import { useSelectedIdeaData } from "../hooks/useSelectedIdeaData";
```

**Render Logic**:
```
1. If conversationId === null -> InlineIdeaEmptyState
2. If isLoading -> ProjectDraftSkeleton
3. If error -> InlineIdeaError
4. If !idea -> InlineIdeaEmptyState (no idea data for this conversation)
5. Otherwise -> ReadOnlyWrapper with ProjectDraftContent
```

**Read-Only Implementation**:
```tsx
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
    onUpdate={() => {}} {/* No-op handler */}
  />
</div>
```

---

### 3.2 useSelectedIdeaData Hook (NEW)

**Purpose**: React Query hook for fetching idea data when a conversation is selected.

**Responsibility (SRP)**: Single responsibility - data fetching for selected idea. Does NOT manage selection state.

**Interface**:
```typescript
interface UseSelectedIdeaDataReturn {
  idea: Idea | null;
  isLoading: boolean;
  error: string | null;
}

function useSelectedIdeaData(conversationId: number | null): UseSelectedIdeaDataReturn
```

**Dependencies**:
```typescript
// MUST REUSE
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";
import type { Idea, IdeaGetResponse } from "@/types";
```

**Implementation Pattern** (following `useConversationResearchRuns`):
```typescript
export function useSelectedIdeaData(conversationId: number | null): UseSelectedIdeaDataReturn {
  const { data, isLoading, error } = useQuery({
    queryKey: ["selected-idea", conversationId],
    queryFn: async () => {
      const response = await apiFetch<IdeaGetResponse>(
        `/conversations/${conversationId}/idea`
      );
      return response.idea;
    },
    enabled: conversationId !== null,
    staleTime: 60 * 1000, // 1 minute - idea content changes less frequently
    gcTime: 5 * 60 * 1000, // 5 minutes cache
  });

  return {
    idea: data ?? null,
    isLoading: conversationId !== null && isLoading,
    error: error instanceof Error
      ? error.message
      : error
        ? "Couldn't load idea. Please try again."
        : null,
  };
}
```

---

### 3.3 IdeationQueueCard (MODIFIED)

**Current Purpose**: Display a single idea card in the queue.

**Modified Purpose**: Display a single idea card with selection state awareness.

**Responsibility (SRP)**: Unchanged - displays a card. Extended to show selection state and call selection callback.

**Props Interface Changes**:
```typescript
// Current
export interface IdeationQueueCardProps {
  id: number;
  title: string;
  abstract: string | null;
  status: IdeaStatus;
  createdAt: string;
  updatedAt: string;
}

// Modified - add selection props
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

**Click Handler Change**:
```typescript
// Current
const handleCardClick = () => {
  router.push(`/conversations/${id}`);
};

// Modified - call onSelect if provided, otherwise navigate (backward compatible)
const handleCardClick = () => {
  if (onSelect) {
    onSelect(id);
  } else {
    router.push(`/conversations/${id}`);
  }
};
```

**Selection Styling**:
```typescript
// Current styling
className={cn(
  "group cursor-pointer rounded-xl border border-slate-800 bg-slate-900/50 p-4",
  "transition-all hover:border-slate-700 hover:bg-slate-900/80"
)}

// Modified - add selection state
className={cn(
  "group cursor-pointer rounded-xl border border-slate-800 bg-slate-900/50 p-4",
  "transition-all hover:border-slate-700 hover:bg-slate-900/80",
  isSelected && "ring-2 ring-sky-500 border-sky-500/50 bg-slate-900/80"
)}
```

---

### 3.4 IdeationQueueList (MODIFIED)

**Purpose**: Render the list of idea cards.

**Responsibility (SRP)**: Unchanged - renders list and passes props to children.

**Props Interface Changes**:
```typescript
// Current
export interface IdeationQueueListProps {
  conversations: Conversation[];
  emptyMessage?: string;
}

// Modified - add selection props to pass through
export interface IdeationQueueListProps {
  conversations: Conversation[];
  emptyMessage?: string;
  // NEW: Selection props (optional for backward compatibility)
  selectedId?: number | null;
  onSelect?: (id: number) => void;
}
```

**Implementation Change**:
```typescript
export function IdeationQueueList({
  conversations,
  emptyMessage,
  selectedId,
  onSelect
}: IdeationQueueListProps) {
  // ...existing empty check...

  return (
    <div className="grid grid-cols-1 gap-4">
      {conversations.map(conversation => (
        <IdeationQueueCard
          key={conversation.id}
          id={conversation.id}
          title={conversation.ideaTitle || conversation.title || "Untitled Idea"}
          abstract={conversation.ideaAbstract ?? null}
          status={deriveIdeaStatus(conversation)}
          createdAt={conversation.createdAt}
          updatedAt={conversation.updatedAt}
          // NEW: Pass selection props
          isSelected={selectedId === conversation.id}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
```

---

### 3.5 conversations/page.tsx (MODIFIED)

**Purpose**: Page component orchestrating the conversations view.

**Responsibility Change**: Extended to manage selection state (appropriate for page-level orchestration).

**State Addition**:
```typescript
const [selectedId, setSelectedId] = useState<number | null>(null);
```

**Integration**:
```tsx
export default function ConversationsPage() {
  const { conversations, isLoading } = useDashboard();
  const { searchTerm, setSearchTerm, filteredConversations } =
    useConversationsFilter(conversations);
  const [selectedId, setSelectedId] = useState<number | null>(null); // NEW

  const hasActiveSearch = searchTerm.trim() !== "";

  return (
    <>
      {/* Main Card */}
      <PageCard>
        <div className="flex flex-col gap-6 p-6">
          <IdeationQueueHeader
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
            totalCount={conversations.length}
            filteredCount={filteredConversations.length}
          />

          {isLoading ? (
            <IdeationQueueSkeleton />
          ) : (
            <IdeationQueueList
              conversations={filteredConversations}
              emptyMessage={hasActiveSearch ? "No ideas match your search" : undefined}
              selectedId={selectedId}           // NEW
              onSelect={setSelectedId}          // NEW
            />
          )}
        </div>
      </PageCard>

      {/* Inline Idea View Card */}
      <PageCard>
        <div className="p-6">
          <InlineIdeaView conversationId={selectedId} />  {/* NEW */}
        </div>
      </PageCard>
    </>
  );
}
```

---

## 4. Data Flow Diagram

```
User clicks IdeationQueueCard
           |
           v
IdeationQueueCard.handleCardClick()
           |
           | calls onSelect(id)
           v
IdeationQueueList.onSelect (passed through)
           |
           | calls onSelect(id)
           v
conversations/page.tsx setSelectedId(id)
           |
           | state update triggers re-render
           v
+----------+----------+
|                     |
v                     v
IdeationQueueList     InlineIdeaView
receives              receives
selectedId={id}       conversationId={id}
                              |
                              | useSelectedIdeaData(id) triggered
                              v
                      React Query fetches
                      /conversations/{id}/idea
                              |
                              v
                      Returns { idea, isLoading, error }
                              |
                              v
                      InlineIdeaView renders:
                      - Loading: ProjectDraftSkeleton
                      - Error: Error message
                      - Success: ProjectDraftContent (read-only)
```

### Query Caching Behavior

```
User selects Card A (id=1)
           |
           v
Query: ["selected-idea", 1] -> FETCH -> Cache
           |
User selects Card B (id=2)
           |
           v
Query: ["selected-idea", 2] -> FETCH -> Cache
           |
User selects Card A again (id=1)
           |
           v
Query: ["selected-idea", 1] -> CACHE HIT (if < staleTime)
```

---

## 5. Type Definitions

### New Types (add to `ideation-queue.types.ts`)

```typescript
// ============================================================================
// Inline Idea View Types
// ============================================================================

/**
 * Props for InlineIdeaView component
 * Focused interface per ISP - only needs conversation ID
 */
export interface InlineIdeaViewProps {
  conversationId: number | null;
}

/**
 * Return type for useSelectedIdeaData hook
 */
export interface UseSelectedIdeaDataReturn {
  idea: Idea | null;
  isLoading: boolean;
  error: string | null;
}
```

### Modified Types (update existing in `ideation-queue.types.ts`)

```typescript
/**
 * Props for IdeationQueueCard component (ISP-compliant: focused interface)
 * MODIFIED: Added optional selection props for inline view support
 */
export interface IdeationQueueCardProps {
  id: number;
  title: string;
  abstract: string | null;
  status: IdeaStatus;
  createdAt: string;
  updatedAt: string;
  /** Whether this card is currently selected for inline view */
  isSelected?: boolean;
  /** Callback when card is selected (if not provided, defaults to navigation) */
  onSelect?: (id: number) => void;
}

/**
 * Props for IdeationQueueList component
 * MODIFIED: Added optional selection props for inline view support
 */
export interface IdeationQueueListProps {
  conversations: Conversation[];
  emptyMessage?: string;
  /** ID of currently selected conversation */
  selectedId?: number | null;
  /** Callback when a conversation is selected */
  onSelect?: (id: number) => void;
}
```

### Import Statements (for reference)

```typescript
// In InlineIdeaView.tsx
import type { Idea } from "@/types";
import type { InlineIdeaViewProps, UseSelectedIdeaDataReturn } from "../types/ideation-queue.types";

// In useSelectedIdeaData.ts
import type { Idea, IdeaGetResponse } from "@/types";
import type { UseSelectedIdeaDataReturn } from "../types/ideation-queue.types";
```

---

## 6. SOLID Analysis

### S - Single Responsibility Principle

| Component | Single Responsibility | Verified |
|-----------|----------------------|----------|
| `InlineIdeaView` | Coordinates display of idea content based on data state | Yes |
| `useSelectedIdeaData` | Fetches idea data for a given conversation ID | Yes |
| `IdeationQueueCard` | Displays a single idea card (extended with selection visual) | Yes |
| `IdeationQueueList` | Renders list of cards, passes props through | Yes |
| `conversations/page.tsx` | Orchestrates page-level state and composition | Yes |

**No violation**: Each component/hook has exactly one reason to change.

### O - Open/Closed Principle

| Extension Point | How Extended | Closed For Modification |
|-----------------|--------------|------------------------|
| `IdeationQueueCard` click | Accept optional `onSelect` callback | Original navigation preserved via default behavior |
| `IdeationQueueList` selection | Accept optional `selectedId` + `onSelect` | Original behavior unchanged when not provided |
| Selection styling | Via CSS class composition (`cn()`) | Base styles unchanged |

**Backward Compatible**: All changes use optional props with default behaviors, ensuring existing usage continues to work.

### L - Liskov Substitution Principle

| Abstraction | Implementations | Substitutable |
|-------------|-----------------|---------------|
| `IdeationQueueCardProps` | Original card, Selected card | Yes - both render valid cards |
| Empty state display | `IdeationQueueEmpty`, `InlineIdeaEmptyState` | Yes - both render valid empty states |

**No violation**: Extended components remain substitutable for their base usage.

### I - Interface Segregation Principle

| Interface | Props Count | Minimal & Focused |
|-----------|-------------|-------------------|
| `InlineIdeaViewProps` | 1 (`conversationId`) | Yes - only what's needed |
| `UseSelectedIdeaDataReturn` | 3 (`idea`, `isLoading`, `error`) | Yes - standard data hook return |
| `IdeationQueueCardProps` (new) | 8 (6 original + 2 optional) | Yes - optional props don't burden callers |

**ISP Compliant**: Optional props ensure callers only provide what they need.

### D - Dependency Inversion Principle

| Component | Depends On | Abstraction |
|-----------|------------|-------------|
| `InlineIdeaView` | `useSelectedIdeaData` | Hook abstraction (not direct API) |
| `useSelectedIdeaData` | `apiFetch`, `useQuery` | Library abstractions |
| `IdeationQueueCard` | `onSelect?: (id) => void` | Callback abstraction |
| `conversations/page.tsx` | `InlineIdeaView` | Component abstraction |

**DIP Compliant**: High-level components depend on abstractions (hooks, callbacks), not concrete implementations.

---

## 7. Assets Usage Summary

### MUST REUSE (Direct Imports)

| Asset | Import Statement | Usage |
|-------|------------------|-------|
| `ProjectDraftContent` | `import { ProjectDraftContent } from "@/features/project-draft/components/ProjectDraftContent"` | Core content display in InlineIdeaView |
| `ProjectDraftSkeleton` | `import { ProjectDraftSkeleton } from "@/features/project-draft/components/ProjectDraftSkeleton"` | Loading state |
| `apiFetch` | `import { apiFetch } from "@/shared/lib/api-client"` | API calls in hook |
| `useQuery` | `import { useQuery } from "@tanstack/react-query"` | Data fetching |
| `cn` | `import { cn } from "@/shared/lib/utils"` | Class merging for selection styles |
| `Eye` | `import { Eye } from "lucide-react"` | View mode badge icon |
| `PageCard` | `import { PageCard } from "@/shared/components/PageCard"` | Container (already used) |
| `Idea`, `IdeaGetResponse` | `import type { Idea, IdeaGetResponse } from "@/types"` | Type safety |

### PATTERN REUSE

| Pattern | Source | Adaptation |
|---------|--------|------------|
| React Query hook structure | `useConversationResearchRuns` | Change endpoint, return type |
| Empty state layout | `IdeationQueueEmpty` | New message/icon for inline view |
| Selection ring style | Input focus patterns in codebase | `ring-2 ring-sky-500` |

### CREATE NEW

| Asset | Why New |
|-------|---------|
| `InlineIdeaView` | New composition requirement - wrapper + states + read-only mode |
| `useSelectedIdeaData` | New data fetching requirement - idea endpoint with enabled conditional |
| Selection props | New behavioral requirement - not existing in types |

---

## 8. Error Handling Strategy

### Loading States

1. **Initial load (no selection)**: Empty state with instruction message
2. **Selection made**: `ProjectDraftSkeleton` while fetching
3. **Cache hit**: Instant display (no loading shown)

### Error States

```tsx
// In InlineIdeaView
if (error) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="rounded-lg bg-red-500/10 p-4 text-red-400">
        <p className="text-sm">{error}</p>
        <button
          onClick={() => refetch?.()}
          className="mt-2 text-xs underline hover:no-underline"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
```

### Edge Cases

| Case | Handling |
|------|----------|
| Conversation has no idea yet | Show "No idea generated yet" message |
| API returns 404 | Caught by error state |
| User rapidly switches selections | React Query cancels stale requests automatically |
| Conversation deleted while viewing | Error on next fetch, clear selection |

---

## 9. Implementation Order

### Phase 1: Types (1 file)
1. Add types to `ideation-queue.types.ts`

### Phase 2: Hook (1 file)
1. Create `useSelectedIdeaData.ts`
2. Test hook in isolation

### Phase 3: Card Selection (2 files)
1. Modify `IdeationQueueCard.tsx` - add props, styling, click handler
2. Modify `IdeationQueueList.tsx` - pass props through

### Phase 4: Inline View (1 file)
1. Create `InlineIdeaView.tsx` with all states

### Phase 5: Integration (2 files)
1. Update `conversations/page.tsx` - add state, wire components
2. Update `index.ts` - export new components

---

## 10. Validation Checklist

### Structure Checks
- [x] Component hierarchy defined
- [x] File paths specified
- [x] No new index files created (using direct imports)

### Type Safety
- [x] Props interfaces defined
- [x] Hook return type defined
- [x] Imports use `@/` path aliases

### SOLID Compliance
- [x] SRP: Each component/hook has single responsibility
- [x] OCP: Extended via optional props, not modification
- [x] LSP: Extended components remain substitutable
- [x] ISP: Focused, minimal interfaces
- [x] DIP: Depend on abstractions (hooks, callbacks)

### Reusability
- [x] MUST REUSE assets identified and import paths specified
- [x] No duplication of existing components
- [x] Patterns followed from existing codebase

---

## Approval Status

- [ ] Pending approval
- [ ] Approved - proceed to Implementation
- [ ] Modified - see feedback below

### Feedback (if modified)
{User feedback will be added here}

---

## APPROVAL REQUIRED

Please review the architecture above. Reply with:
- **"proceed"** or **"yes"** - Continue to Implementation phase
- **"modify: [your feedback]"** - I'll adjust the architecture
- **"elaborate"** - Provide more details and context for review
- **"stop"** - Pause here (progress saved)

Waiting for your approval before continuing...
