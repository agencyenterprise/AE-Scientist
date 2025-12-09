# Planning Phase

## Agent
feature-planner

## Timestamp
2025-12-08

## Input Received
- Context: User request for inline conversation viewing instead of navigation
- Project docs consulted:
    - .agent/README.md
    - .agent/System/frontend_architecture.md
    - .agent/Tasks/ideation-queue-research-runs/

## Reasoning

### Why This Approach

**Read-Only Wrapper Component Approach Selected**

After analyzing the codebase, I recommend creating a read-only wrapper component `InlineIdeaView` that:

1. **Wraps ProjectDraftContent for display-only mode**
   - The existing `ProjectDraftContent` receives `onUpdate` callback and triggers edit modals
   - For read-only mode, we need to intercept/disable these interactions
   - Create a wrapper that passes no-op handlers and hides edit UI elements

2. **Uses local state for selection (not context)**
   - The change is localized to the conversations page
   - No other components need to know about selection state
   - Adding to `DashboardContext` would be over-engineering
   - Local state in `conversations/page.tsx` is sufficient

3. **Fetches idea data on-demand when card selected**
   - Create a new hook `useSelectedIdeaData` that fetches when selection changes
   - Leverage existing API endpoint `GET /api/conversations/{id}/idea`
   - Handle loading and error states inline

**Alternatives Considered but Rejected**

| Alternative | Reason Rejected |
|-------------|----------------|
| Modify ProjectDraftContent for read-only prop | Would add complexity to a working component |
| Add selection to DashboardContext | Over-engineering for page-local feature |
| Use URL query params for selection | Unnecessary URL complexity, local state simpler |
| Create entirely new component | Would duplicate ProjectDraftContent logic |

### Pattern Selection

- **Chose pattern**: Wrapper component with composition
- **Because**: Maintains existing component integrity while adding new behavior
- **Reference**: Similar to how `ProjectDraft` wraps `ProjectDraftContent` but with different controls

### Key Architectural Decision: View-Only Mode

To make ProjectDraftContent read-only, I propose:

1. **Option A: CSS/Pointer-Events Disable** (Recommended)
   - Wrap in a div with `pointer-events-none` on edit buttons
   - Simplest approach, no component changes

2. **Option B: Conditional Edit Prop**
   - Add `isEditable?: boolean` prop to section components
   - More flexible but requires modifying multiple files

3. **Option C: Separate ViewOnlyProjectDraftContent**
   - Create new component that omits edit functionality
   - Clean separation but code duplication

**Recommendation**: Option A for MVP (simplest), with path to Option B if more control needed later.

### Dependencies Identified

1. **IdeationQueueCard.tsx**: Change click handler from navigate to callback
2. **IdeationQueueList.tsx**: Pass selection callback to cards
3. **conversations/page.tsx**: Add selection state and InlineIdeaView
4. **ProjectDraftContent.tsx**: Reused as-is (no changes)
5. **API**: Existing endpoint `GET /api/conversations/{id}/idea`

### Risks & Considerations

| Risk | Mitigation |
|------|------------|
| ProjectDraftContent modals still appearing | Use pointer-events-none on edit buttons area |
| Loading flash when switching selections | Show skeleton during load |
| Performance with rapid selection changes | Debounce selection or cancel in-flight requests |
| User confusion (why can't I edit?) | Add visual indicator "View mode" |
| Scroll position jumps | Smooth scroll to view section on selection |
| Empty second PageCard looks broken | Show helpful empty state message |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| State management | Local useState in page | Feature is page-scoped, no need for context |
| Read-only implementation | CSS pointer-events-none + visual indicator | Minimal changes to existing components |
| Data fetching | New hook useSelectedIdeaData | Clean separation, handles loading/error |
| Card click handler | Callback prop to IdeationQueueList | Allows parent control of behavior |
| Empty state | Friendly message in second PageCard | Better UX than empty card |
| Loading state | Skeleton similar to ProjectDraftSkeleton | Consistent with existing patterns |

## UI/UX Design

### Selection Visual Feedback

When a card is selected:
- Add `ring-2 ring-sky-500` border highlight
- Slight background color change `bg-slate-900/80`

### Inline View Layout

```
+----------------------------------+
| PageCard: Ideation Queue List    |
|  +----------------------------+  |
|  | Card (selected) [ring]     |  |
|  +----------------------------+  |
|  | Card                       |  |
|  +----------------------------+  |
|  | Card                       |  |
|  +----------------------------+  |
+----------------------------------+

+----------------------------------+
| PageCard: Idea Preview           |
|  [VIEW MODE badge]               |
|  +----------------------------+  |
|  | Hypothesis Section         |  |
|  +----------------------------+  |
|  | Related Work Section       |  |
|  +----------------------------+  |
|  | Abstract Section           |  |
|  +----------------------------+  |
|  | Experiments Section        |  |
|  +----------------------------+  |
|  | Expected Outcome Section   |  |
|  +----------------------------+  |
|  | Risk Factors Section       |  |
|  +----------------------------+  |
+----------------------------------+
```

### Empty State

When no conversation is selected:
```
+----------------------------------+
| PageCard: Idea Preview           |
|                                  |
|     [Eye icon]                   |
|     Select an idea above         |
|     to preview its details       |
|                                  |
+----------------------------------+
```

## Output Summary

- Task docs created: `00-context.md`, `01-planning.md`
- PRD to be created: `.agent/Tasks/inline-conversation-view/PRD.md`
- Files to create: 2 new files
- Files to modify: 3 existing files
- Estimated complexity: **Moderate** - primarily frontend component work

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `features/conversation/components/InlineIdeaView.tsx` | Wrapper component for read-only ProjectDraftContent display |
| `features/conversation/hooks/useSelectedIdeaData.ts` | Hook to fetch idea data for selected conversation |

### Modified Files

| File | Changes |
|------|---------|
| `features/conversation/components/IdeationQueueCard.tsx` | Add onSelect callback prop, update click handler |
| `features/conversation/components/IdeationQueueList.tsx` | Pass selectedId and onSelect props |
| `app/(dashboard)/conversations/page.tsx` | Add selection state, render InlineIdeaView |
| `features/conversation/types/ideation-queue.types.ts` | Add props interfaces for selection |
| `features/conversation/index.ts` | Export new components |

## Implementation Phases

### Phase 1: Selection Infrastructure
1. Add `selectedId` state to conversations page
2. Add `onSelect` and `selectedId` props to IdeationQueueList
3. Modify IdeationQueueCard to handle selection (visual + callback)

### Phase 2: Data Fetching
1. Create `useSelectedIdeaData` hook
2. Fetch idea when selection changes
3. Handle loading/error states

### Phase 3: Inline View Component
1. Create `InlineIdeaView` component
2. Render ProjectDraftContent in read-only mode
3. Add empty state component
4. Add "View Mode" indicator

### Phase 4: Integration
1. Wire everything together in conversations page
2. Add selection highlight styling
3. Test complete flow

## For Next Phase (Architecture)

Key considerations for the architect:

1. **Read-Only Enforcement**: Verify pointer-events approach properly disables all edit triggers (section edit buttons, modal triggers).

2. **Loading UX**: Determine if we show skeleton in second PageCard or loading spinner.

3. **Selection Persistence**: Should selection survive page refresh? (Current plan: no, it's transient)

4. **Mobile Responsiveness**: How should two-panel layout adapt on mobile?

5. **Keyboard Navigation**: Should arrow keys navigate selection? (Future enhancement)

6. **Deselection**: Should clicking same card again deselect? Or clicking outside?

## Approval Status
- [ ] Pending approval
- [ ] Approved - proceed to Architecture
- [ ] Modified - see feedback below

### Feedback (if modified)
{User feedback will be added here}
