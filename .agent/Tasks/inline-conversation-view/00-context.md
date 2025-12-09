# Initial Context

## Agent
feature-planner

## Source
User request via chat

## Task Type
Feature Enhancement

## Timestamp
2025-12-08 (created by feature-planner agent)

## Original Request

When clicking on IdeationQueueCardComponent, instead of redirecting to the conversation page (`/conversations/{id}`), open the ProjectDraftContent component in view mode (no editing allowed) below the Main Card in `frontend/src/app/(dashboard)/conversations/page.tsx`.

### User Requirements

1. **Click Behavior Change**: Card click should show conversation inline, not navigate
2. **Component Integration**: Use existing ProjectDraftContent component
3. **View Mode Only**: No editing allowed (read-only mode)
4. **Layout**: Content appears in the second PageCard below the main list
5. **Selection State**: Track which conversation is currently selected
6. **Empty State**: Show appropriate message when no conversation is selected

## Context from User

From the user's recent changes:
- The conversations page now has two PageCard components
- The second PageCard is empty and ready for the Idea view (ProjectDraftContent)
- IdeationQueueCard currently navigates using `router.push('/conversations/${id}')`

## Related Documentation

- `.agent/System/frontend_architecture.md` - Frontend patterns and conventions
- `.agent/Tasks/ideation-queue-research-runs/` - Related feature for research runs display

## Key Technical Findings (from pre-planning research)

### Current Architecture

1. **Conversations Page** (`/conversations/page.tsx`):
   - Uses `useDashboard()` context for conversations list
   - Has two `PageCard` components - one for list, one empty for future content
   - Uses `IdeationQueueList` which renders `IdeationQueueCard` components

2. **IdeationQueueCard** (`/features/conversation/components/IdeationQueueCard.tsx`):
   - Currently calls `router.push('/conversations/${id}')` on click
   - Has expand/collapse functionality for research runs
   - Is memoized for performance

3. **ProjectDraftContent** (`/features/project-draft/components/ProjectDraftContent.tsx`):
   - Requires props: `projectDraft: Idea`, `conversationId: string`, `onUpdate`, `sectionDiffs?`
   - Has editing capabilities via `useSectionEdit` hook
   - Shows sections: Hypothesis, Related Work, Abstract, Experiments, Expected Outcome, Risk Factors

4. **ProjectDraft** (`/features/project-draft/components/ProjectDraft.tsx`):
   - Container component that manages state via hooks
   - Uses `useProjectDraftState`, `useVersionManagement`, `useDiffGeneration`, `useAnimations`
   - Handles title editing, project creation, section updates

5. **Data Fetching**:
   - `useProjectDraftData` hook fetches idea data via `GET /api/conversations/{id}/idea`
   - Requires `ConversationDetail` object to work
   - Has polling for idea generation status

### Existing Types

- `Conversation` (from api-adapters): Basic conversation info for list display
- `ConversationDetail` (from types): Full conversation data including idea
- `Idea` (from api.gen.ts): Project draft data with versions
- `IdeationQueueCardProps`: id, title, abstract, status, createdAt, updatedAt

### DashboardContext Structure

Located in `features/dashboard/contexts/DashboardContext.tsx`:
- Provides: conversations, isLoading, selectConversation, refreshConversations, sort options
- `selectConversation` currently navigates to `/conversations/{id}`

### Gap Analysis

| Aspect | Current State | Required |
|--------|---------------|----------|
| Card click | Navigates to detail page | Should select for inline view |
| Selection state | URL-based (via route param) | Component state (context or local) |
| ProjectDraftContent | Used in detail page only | Need view-only version in list page |
| Data fetching | Per-page (detail page fetches idea) | Per-selection (fetch idea when card selected) |
| Edit capabilities | Full editing in detail page | Read-only in inline view |

## Initial Assessment

**Complexity**: Moderate
- Primary challenge is adapting ProjectDraftContent for read-only mode
- Need to manage selection state at conversation page level
- Data fetching pattern needs to work with selection (not route)
- Must handle empty state gracefully
