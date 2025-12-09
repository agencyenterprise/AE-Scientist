# Inline Conversation View - Product Requirements Document

## Overview

Replace the current navigation behavior of IdeationQueueCard (which redirects to `/conversations/{id}`) with an inline preview that displays the ProjectDraftContent component in view-only mode below the conversation list.

## Status
See planning documents (`00-context.md`, `01-planning.md`) for current status.

## User Stories

- As a user, I want to preview idea details without leaving the ideation queue so that I can quickly browse multiple ideas
- As a user, I want to see the idea content in read-only mode so that I don't accidentally modify it while browsing
- As a user, I want clear visual feedback when I select an idea so that I know which idea I'm viewing
- As a user, I want a helpful empty state when no idea is selected so that I understand how to use the feature

## Requirements

### Functional Requirements

1. **FR-1: Card Click Selection**
   - Clicking an IdeationQueueCard should select that conversation
   - Selection should be tracked in component state
   - Only one conversation can be selected at a time

2. **FR-2: Visual Selection Indicator**
   - Selected card should have a visible border highlight (ring)
   - Background color should change to indicate selection

3. **FR-3: Inline Idea Display**
   - Selected idea's ProjectDraftContent should appear in second PageCard
   - Content should be read-only (no edit modals, no edit buttons active)
   - Display "View Mode" badge/indicator

4. **FR-4: Empty State**
   - When no conversation is selected, show friendly message
   - Message should instruct user to select an idea

5. **FR-5: Loading State**
   - Show skeleton/loading while fetching idea data
   - Handle error states gracefully

### Non-Functional Requirements

1. **NFR-1: Performance**
   - Selection change should feel instant (< 100ms visual feedback)
   - Idea data fetch should use appropriate caching

2. **NFR-2: Accessibility**
   - Selected state should be keyboard accessible
   - Screen readers should announce selection changes

3. **NFR-3: Responsive**
   - Layout should work on tablet and desktop
   - Consider stacking on mobile (future)

## Technical Decisions

See `01-planning.md` for full decisions list.

Key decisions:
- **State Management**: Local useState in page component
- **Read-Only Mode**: CSS pointer-events-none approach
- **Data Fetching**: New useSelectedIdeaData hook

## Reusability Analysis

### Existing Assets to REUSE

| Asset | Location | How Used |
|-------|----------|----------|
| `ProjectDraftContent` | `features/project-draft/components/ProjectDraftContent.tsx` | Core display component |
| `ProjectDraftSkeleton` | `features/project-draft/components/ProjectDraftSkeleton.tsx` | Loading state |
| `PageCard` | `shared/components/PageCard.tsx` | Container for inline view |
| `apiFetch` | `shared/lib/api-client.ts` | API calls |
| `cn` utility | `shared/lib/utils.ts` | Class merging |
| Ring/selection styles | Existing patterns | Visual feedback |

### Similar Features to Reference

| Feature | What to learn |
|---------|---------------|
| `IdeationQueueRunsList` | On-demand data fetching pattern |
| `ProjectDraft` component | How to compose ProjectDraftContent |
| Research detail page | Loading states pattern |

## Implementation Plan

### Phase 1: Selection Infrastructure (Files: 4)

**1.1 Update Types** (`features/conversation/types/ideation-queue.types.ts`)
- Add `onSelect?: (id: number) => void` to IdeationQueueCardProps
- Add `selectedId?: number | null` to IdeationQueueCardProps
- Add `selectedId?: number | null` to IdeationQueueListProps
- Add `onSelect?: (id: number) => void` to IdeationQueueListProps

**1.2 Update IdeationQueueCard** (`features/conversation/components/IdeationQueueCard.tsx`)
- Add `onSelect` and `selectedId` props
- Change `handleCardClick` to call `onSelect?.(id)` instead of navigate
- Add conditional ring/background classes when `selectedId === id`

**1.3 Update IdeationQueueList** (`features/conversation/components/IdeationQueueList.tsx`)
- Accept and pass through `selectedId` and `onSelect` props

**1.4 Update conversations/page.tsx**
- Add `const [selectedId, setSelectedId] = useState<number | null>(null)`
- Pass `selectedId` and `onSelect={setSelectedId}` to IdeationQueueList

### Phase 2: Data Fetching Hook (Files: 1)

**2.1 Create useSelectedIdeaData** (`features/conversation/hooks/useSelectedIdeaData.ts`)
```typescript
interface UseSelectedIdeaDataReturn {
  idea: Idea | null;
  isLoading: boolean;
  error: string | null;
}

function useSelectedIdeaData(conversationId: number | null): UseSelectedIdeaDataReturn
```
- Returns null when conversationId is null
- Fetches from `/api/conversations/{id}/idea`
- Handles loading and error states

### Phase 3: Inline View Component (Files: 1)

**3.1 Create InlineIdeaView** (`features/conversation/components/InlineIdeaView.tsx`)
- Props: `conversationId: number | null`
- When null: render empty state
- When loading: render skeleton
- When error: render error message
- When data: render ProjectDraftContent with read-only wrapper

```tsx
// Read-only wrapper approach
<div className="relative">
  {/* View Mode indicator */}
  <div className="mb-4 flex items-center gap-2">
    <Eye className="h-4 w-4 text-slate-400" />
    <span className="text-xs uppercase tracking-wide text-slate-400">View Mode</span>
  </div>

  {/* Content with disabled interactions */}
  <div className="[&_button]:pointer-events-none [&_button]:opacity-50">
    <ProjectDraftContent
      projectDraft={idea}
      conversationId={conversationId.toString()}
      onUpdate={() => {}} // No-op
    />
  </div>
</div>
```

### Phase 4: Integration (Files: 1)

**4.1 Complete conversations/page.tsx**
- Import InlineIdeaView
- Render in second PageCard
- Wire up complete flow

## File Structure (Proposed)

See `01-planning.md` `files.pending` for full list.

```
features/conversation/
  components/
    InlineIdeaView.tsx       # NEW
    IdeationQueueCard.tsx    # MODIFIED
    IdeationQueueList.tsx    # MODIFIED
  hooks/
    useSelectedIdeaData.ts   # NEW
  types/
    ideation-queue.types.ts  # MODIFIED

app/(dashboard)/conversations/
  page.tsx                   # MODIFIED
```

## UI Specifications

### Card Selection Styles

```typescript
// In IdeationQueueCard
className={cn(
  "group cursor-pointer rounded-xl border border-slate-800 bg-slate-900/50 p-4",
  "transition-all hover:border-slate-700 hover:bg-slate-900/80",
  selectedId === id && "ring-2 ring-sky-500 border-sky-500/50 bg-slate-900/80"
)}
```

### Empty State Design

```tsx
<div className="flex flex-col items-center justify-center py-16 text-center">
  <Eye className="h-12 w-12 text-slate-600 mb-4" />
  <h3 className="text-sm font-medium text-slate-300 mb-1">
    Select an idea
  </h3>
  <p className="text-xs text-slate-500">
    Click on an idea above to preview its details
  </p>
</div>
```

### Loading State

Reuse existing `ProjectDraftSkeleton` component within PageCard.

## Related Documentation

- `.agent/System/frontend_architecture.md` - Frontend patterns
- `.agent/Tasks/ideation-queue-research-runs/` - Similar expandable pattern
- `/features/project-draft/` - ProjectDraftContent source

## Testing Considerations

1. **Selection toggles correctly** - Click card, verify selection state
2. **Data loads on selection** - Verify API call made
3. **Read-only mode works** - Click edit buttons, verify no modals open
4. **Empty state displays** - Before any selection
5. **Loading state displays** - During fetch
6. **Error state handles gracefully** - Simulate API failure

## Future Enhancements (Out of Scope)

- Keyboard navigation (arrow keys)
- Selection persistence in URL
- Mobile stacked layout
- Deselection by clicking same card
- Animation/transition on view switch
