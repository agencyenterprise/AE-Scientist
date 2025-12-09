# Ideation Queue Enhancement - Product Requirements Document

## Overview

Rename the "Conversations" page to "Ideation Queue" and enhance it to provide a more useful view of research ideas with status badges, hypothesis previews, and filtering/sorting capabilities. This aligns with Flavio's original naming and provides better context for users managing their research pipeline.

## Status

- [x] Planning
- [x] Architecture
- [x] Implementation
- [x] Testing
- [x] Complete

## User Stories

### Primary User Stories

1. **As a researcher**, I want to see a meaningful preview of each hypothesis so I can quickly identify which idea I'm looking for without clicking into each one.

2. **As a researcher**, I want to see the status of each idea (Pending launch, In research, Completed, Failed) so I know which ideas need attention.

3. **As a researcher**, I want to sort my ideas by different criteria (newest, oldest, status) so I can organize my workflow.

4. **As a researcher**, I want to filter ideas by status so I can focus on specific stages of my research pipeline.

5. **As a user**, I want the "Conversations" page renamed to "Ideation Queue" so the terminology reflects its purpose.

## Requirements

### Functional Requirements

#### Page Renaming
1. Rename page title from "Conversations" to "Ideation Queue"
2. Update header icon to match ideation theme (Lightbulb instead of MessageSquare)
3. Update subtitle/count text to use "ideas" terminology

#### Idea Cards/Rows - Enhanced Display
Each idea row must display:
1. **Hypothesis Title** - Truncated but readable (ideaTitle or title fallback)
2. **Snippet/Abstract** - First ~200 characters of ideaAbstract or ideaHypothesis
3. **Status Badge** - Visual indicator with color coding:
   - "No idea" (slate) - No ideaTitle/ideaAbstract present
   - "Pending launch" (amber) - Has idea but no research run
   - "In research" (sky blue with spinner) - Active research run
   - "Completed" (emerald) - Research run completed
   - "Failed" (red) - Research run failed
4. **Created Date** - When the conversation was imported
5. **Last Updated Date** - Most recent activity

#### Sorting
Support sorting by:
- Newest first (default)
- Oldest first
- Status (grouped by status type)
- Title (alphabetical)

#### Filtering
Support filtering by:
- All (default)
- Status: No idea, Pending, In research, Completed, Failed
- Search term (existing functionality)

#### Responsive Layout
- Desktop: Table view with all columns visible
- Tablet: Condensed table or card view
- Mobile: Card view with essential information

### Non-Functional Requirements

1. **Performance**: List should render smoothly with 100+ items
2. **Accessibility**: Status badges must have accessible text for screen readers
3. **Consistency**: Visual style must match existing research board components
4. **Backward Compatibility**: URL `/conversations` should still work (no route change needed initially)

## Technical Decisions

### Based on project documentation:

- **Pattern**: Feature-based component organization (per frontend_architecture.md)
- **SOP**: Follow frontend_features.md for component structure
- **Dependencies**:
  - Existing conversation data structures
  - Research utils for status badge styling (reuse from research feature)
  - date-fns for relative time formatting (already in use)

### Status Derivation Strategy

For MVP, derive status from existing data without backend changes:

```typescript
function deriveIdeaStatus(conversation: Conversation): IdeaStatus {
  // Check if conversation has associated research runs
  // This requires either:
  // A) Backend endpoint to include latest research status
  // B) Join with useRecentResearch data on frontend

  // MVP approach based on available fields:
  if (!conversation.ideaTitle && !conversation.ideaAbstract) {
    return "no_idea";
  }
  // Without research run data, default to "pending"
  return "pending_launch";
}
```

**Recommendation**: For full status support, we should enhance the backend `ConversationListItem` to include `latest_research_status` field in a future iteration.

### Component Architecture

Enhance existing conversation feature rather than create new feature:

```
features/conversation/
├── components/
│   ├── IdeationQueueHeader.tsx        # NEW - Renamed header
│   ├── IdeationQueueTable.tsx         # NEW - Enhanced table
│   ├── IdeationQueueRow.tsx           # NEW - Individual row/card
│   ├── IdeationQueueFilters.tsx       # NEW - Filter controls
│   ├── IdeationQueueEmpty.tsx         # NEW - Empty state
│   ├── ConversationsBoardHeader.tsx   # DEPRECATED - Keep for reference
│   ├── ConversationsBoardTable.tsx    # DEPRECATED - Keep for reference
│   └── ... (existing components)
├── hooks/
│   ├── useConversationsFilter.ts      # MODIFY - Add status filter
│   └── useIdeationQueueSort.ts        # NEW - Sorting logic
├── utils/
│   └── ideation-queue-utils.ts        # NEW - Status derivation, etc.
└── types/
    └── ideation-queue.types.ts        # NEW - Status types
```

## Reusability Analysis

### Existing Assets to REUSE

- [x] `getStatusBadge()` from `features/research/utils/research-utils.tsx` - Adapt for ideation statuses
- [x] `formatRelativeTime()` from `shared/lib/date-utils.ts` - Already extracted
- [x] Filter UI pattern from `research-logs-list.tsx` - Filter button configuration
- [x] `cn()` utility from `shared/lib/utils` - Class merging
- [x] Existing `useConversationsFilter` hook - Extend, don't replace

### Similar Features to Reference

- `research-board-card.tsx`: Card structure, status badges
- `ResearchBoardTable.tsx`: Table layout, action buttons
- `ConversationCard.tsx`: Existing conversation display (too complex, simplify)

### Needs Codebase Analysis

- [x] Yes - Need to check if backend can provide research status per conversation

## Implementation Plan

### Phase 1: Utilities and Types
- [ ] Create `ideation-queue.types.ts` with status types
- [ ] Create `ideation-queue-utils.ts` with status derivation and badge functions
- [ ] Create status badge component adapting research patterns

### Phase 2: Core Components
- [ ] Create `IdeationQueueHeader.tsx` - New header with Lightbulb icon
- [ ] Create `IdeationQueueRow.tsx` - Enhanced row with preview
- [ ] Create `IdeationQueueTable.tsx` - Table wrapper
- [ ] Create `IdeationQueueEmpty.tsx` - Empty state

### Phase 3: Filtering and Sorting
- [ ] Create `IdeationQueueFilters.tsx` - Status filter buttons
- [ ] Extend `useConversationsFilter.ts` to support status filtering
- [ ] Create `useIdeationQueueSort.ts` for sorting options

### Phase 4: Page Integration
- [ ] Update `/app/(dashboard)/conversations/page.tsx` to use new components
- [ ] Keep existing components for gradual migration
- [ ] Test all scenarios

### Phase 5: Polish and Testing
- [ ] Verify responsive layouts
- [ ] Test with empty state
- [ ] Test with various status combinations
- [ ] Update feature exports in `index.ts`

## File Structure (Proposed)

```
frontend/src/
├── app/(dashboard)/
│   └── conversations/
│       └── page.tsx                    # MODIFY - Use new components
│
└── features/conversation/
    ├── components/
    │   ├── IdeationQueueHeader.tsx     # NEW
    │   ├── IdeationQueueTable.tsx      # NEW
    │   ├── IdeationQueueRow.tsx        # NEW
    │   ├── IdeationQueueFilters.tsx    # NEW
    │   ├── IdeationQueueEmpty.tsx      # NEW
    │   ├── ConversationsBoardHeader.tsx  # KEEP (deprecated)
    │   ├── ConversationsBoardTable.tsx   # KEEP (deprecated)
    │   └── ... (other existing)
    ├── hooks/
    │   ├── useConversationsFilter.ts   # MODIFY
    │   └── useIdeationQueueSort.ts     # NEW
    ├── utils/
    │   └── ideation-queue-utils.ts     # NEW
    ├── types/
    │   └── ideation-queue.types.ts     # NEW
    └── index.ts                        # MODIFY - Add new exports
```

## UI Design Specifications

### Header
```
[Lightbulb Icon]
Ideation Queue
{count} idea{s} | Showing {filtered} of {total}

[Search Input]                      [Status Filters: All | Pending | Running | Completed | Failed]
```

### Table Row Layout
```
+--------------------------------------------------------------------------------+
| [Status Badge]  | Title (truncated)                    | Created  | Updated    |
|                 | Abstract preview (line-clamp-2)...   |          |            |
|                 |                                      |          | [View ->]  |
+--------------------------------------------------------------------------------+
```

### Status Badge Colors (matching research feature)
- No idea: `bg-slate-500/15 text-slate-400`
- Pending launch: `bg-amber-500/15 text-amber-400`
- In research: `bg-sky-500/15 text-sky-400` (with spinner)
- Completed: `bg-emerald-500/15 text-emerald-400`
- Failed: `bg-red-500/15 text-red-400`

## API Considerations

### Current API
The `/api/conversations` endpoint returns `ConversationListResponse` which does NOT include research run status.

### Future Enhancement (Not in MVP)
Add `latest_research_status` to `ConversationListItem` schema:
```json
{
  "id": 1,
  "title": "...",
  "idea_title": "...",
  "idea_abstract": "...",
  "latest_research_status": "running" | "completed" | "failed" | null,
  ...
}
```

### MVP Workaround
For MVP, status will be derived from existing fields:
- Has ideaTitle/ideaAbstract? -> "Pending launch"
- No ideaTitle/ideaAbstract? -> "No idea"

## Acceptance Criteria

1. [ ] Page header displays "Ideation Queue" with Lightbulb icon
2. [ ] Each row shows: status badge, title, abstract preview, created date, updated date
3. [ ] Abstract preview is truncated to ~200 chars with ellipsis
4. [ ] Status badges use consistent colors matching research feature
5. [ ] Sorting dropdown with options: Newest, Oldest, Title (A-Z), Title (Z-A)
6. [ ] Filter buttons for status categories
7. [ ] Search functionality still works
8. [ ] Empty state displays when no ideas match filters
9. [ ] Responsive layout works on mobile, tablet, desktop
10. [ ] No console errors or warnings
11. [ ] TypeScript compiles without errors

## Related Documentation

- `.agent/System/frontend_architecture.md` - Feature-based architecture
- `.agent/SOP/frontend_features.md` - Feature creation guidelines
- `.agent/SOP/frontend_pages.md` - Page creation guidelines
- `.agent/Tasks/research-history-home/PRD.md` - Similar feature for reference

## Progress Log

### 2025-12-05
- Created initial PRD based on user requirements
- Analyzed existing conversations page implementation
- Identified reusable components from research feature
- Determined MVP status derivation strategy
- Created 00-context.md and 01-planning.md breadcrumbs
- Completed codebase analysis (01a-reusable-assets.md)
- Completed architecture design (02-architecture.md) - Card-based layout
- Completed Next.js 15 guidance (02a-nextjs-guidance.md)
- **Implementation completed:**
  - Created `types/ideation-queue.types.ts` (IdeaStatus, StatusFilterOption, props interfaces)
  - Created `utils/ideation-queue-utils.tsx` (configs, deriveIdeaStatus, getIdeaStatusBadge)
  - Created `components/IdeationQueueEmpty.tsx` (empty state)
  - Created `components/IdeationQueueFilters.tsx` (status filter buttons)
  - Created `components/IdeationQueueCard.tsx` (memoized card component)
  - Created `components/IdeationQueueList.tsx` (responsive grid container)
  - Created `components/IdeationQueueHeader.tsx` (header with search and filters)
  - Extended `hooks/useConversationsFilter.ts` (added statusFilter state and logic)
  - Updated `index.ts` (added all new exports)
  - Updated `conversations/page.tsx` (integrated new components)
  - Updated `shared/components/Header.tsx` (navigation text: Conversations → Ideation Queue)
  - TypeScript compilation: PASS
  - Created 03-implementation.md breadcrumb
- **Task marked complete by user**
