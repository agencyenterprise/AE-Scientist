# Ideation Queue Research Runs - Product Requirements Document

## Overview

Enhance the Ideation Queue to display research runs associated with each idea, allowing users to see the history of research attempts and navigate directly to run details. This builds on the existing ideation-queue-enhancement feature which displays ideas with status badges.

## Status

- [x] Planning
- [x] Architecture
- [x] Implementation
- [ ] Testing (manual testing checklist pending)
- [ ] Complete (pending approval)

## User Stories

### Primary User Stories

1. **As a researcher**, I want to see all research runs associated with each idea so I can track the history of experiments on that idea.

2. **As a researcher**, I want to see the status of each research run (pending, running, completed, failed) so I know which runs are active or have results.

3. **As a researcher**, I want to click on a research run to navigate to the Research tab and see the full details, artifacts, and logs from that run.

4. **As a researcher**, I want to identify at a glance which ideas have active (in-progress) research runs so I can monitor ongoing work.

5. **As a researcher**, I want the research runs displayed in a clear hierarchy under each idea so I understand the relationship between ideas and runs.

## Requirements

### Functional Requirements

#### Research Runs Display
1. Each idea card must show a list of associated research runs (if any)
2. Research runs should be displayed as sub-items under the idea card
3. Each research run must show:
   - Run ID (truncated, e.g., "rp-abc123...")
   - Status badge (pending, running, completed, failed)
   - Created date (relative time, e.g., "2 hours ago")
   - GPU type (if available)
4. Research runs should be ordered by creation date (newest first)
5. Ideas with no research runs should show a subtle "No runs yet" indicator

#### Status Badges for Research Runs
- **Pending**: Amber badge - run queued but not yet started
- **Running**: Sky blue badge with subtle animation - actively processing
- **Completed**: Emerald badge - successfully finished
- **Failed**: Red badge - encountered an error

#### Navigation
1. Clicking on a research run navigates to `/research/{runId}` (existing route)
2. Clicking on the idea card itself should still navigate to `/conversations/{id}`
3. Navigation should be clear (visual affordance for clickable runs)

#### Data Fetching Strategy
1. **Option A (Implemented)**: Expand/collapse pattern (expanded by default)
   - Idea cards start with runs expanded (showing research runs immediately)
   - Clicking "Hide runs" collapses the runs section
   - Runs are fetched on component mount for each visible card

2. **Option B**: Always fetch
   - Modify list endpoint to include research_runs
   - Higher initial load but no secondary requests

#### Real-time Updates (Future Enhancement)
1. For ideas with "running" status, consider polling to update run status
2. This is a stretch goal and not required for MVP

### Non-Functional Requirements

1. **Performance**: Page should render smoothly with 50+ ideas, each with multiple runs
2. **Accessibility**: Status badges must have accessible labels for screen readers
3. **Consistency**: Use same status badge styling as existing Research tab
4. **Mobile Responsiveness**: Research runs should stack appropriately on mobile

## Technical Decisions

### Based on project documentation:

- **Pattern**: Feature-based component organization (per frontend_architecture.md)
- **SOP**: Follow frontend_features.md and frontend_api_hooks.md
- **Dependencies**:
  - Existing `IdeationQueueCard` component (modify)
  - Research run types from `@/types/research`
  - Status badge utilities from research feature
  - date-fns for relative time formatting

### Data Fetching Strategy Decision

**Recommended: Hybrid Approach**
- Use existing `/api/conversations` list (without runs) for initial render
- Fetch runs on-demand via `/api/conversations/{id}` when user expands a card
- Cache fetched runs in React Query for subsequent renders

**Rationale**:
1. Backend already has `ConversationResponse.research_runs` in detail endpoint
2. Avoids modifying the list endpoint (less backend work)
3. Reduces initial page load for users with many ideas
4. React Query caching provides good UX for repeated expansions

### Component Architecture

Modify existing conversation feature rather than create new feature:

```
features/conversation/
  components/
    IdeationQueueCard.tsx           # MODIFY - Add expandable runs section
    IdeationQueueRunItem.tsx        # NEW - Individual research run row
    IdeationQueueRunsList.tsx       # NEW - Container for runs list
  hooks/
    useConversationResearchRuns.ts  # NEW - Fetch runs for a conversation
  types/
    ideation-queue.types.ts         # MODIFY - Add run-related types
  utils/
    ideation-queue-utils.tsx        # MODIFY - Add run status badge
```

## Reusability Analysis

### Existing Assets to REUSE

- [x] `getStatusBadge()` pattern from `features/research/utils/research-utils.tsx` - Adapt for run status
- [x] `formatRelativeTime()` from `shared/lib/date-utils.ts` - Already available
- [x] `ResearchRunSummary` type from `@/types/index` -> backend model
- [x] `apiFetch` from `shared/lib/api-client.ts` - For API calls
- [x] `cn()` utility from `shared/lib/utils` - Class merging
- [x] Existing `IdeationQueueCard` - Base to modify

### Similar Features to Reference

- `research-board-card.tsx`: Status badge patterns
- `ResearchHistoryCard.tsx`: Run card layout inspiration
- Existing `IdeationQueueCard.tsx`: Current card structure

### Needs Codebase Analysis

- [x] No - Backend already supports this, primarily frontend work

## Implementation Plan

### Phase 1: Types and Utilities

- [ ] Extend `ideation-queue.types.ts` with research run display types
- [ ] Add `RunStatusConfig` and `getRunStatusBadge()` to utils
- [ ] Create `ResearchRunDisplay` interface for frontend use

### Phase 2: Data Fetching Hook

- [ ] Create `useConversationResearchRuns.ts` hook
- [ ] Fetch from `/api/conversations/{id}` and extract `research_runs`
- [ ] Add React Query caching with appropriate stale time
- [ ] Handle loading and error states

### Phase 3: Run Display Components

- [ ] Create `IdeationQueueRunItem.tsx` - Single run row with status badge
- [ ] Create `IdeationQueueRunsList.tsx` - List container with empty state
- [ ] Style to clearly show hierarchy (indentation, visual grouping)

### Phase 4: Card Integration

- [ ] Modify `IdeationQueueCard.tsx` to support expansion
- [ ] Add expand/collapse toggle or always-visible runs section
- [ ] Integrate `useConversationResearchRuns` hook
- [ ] Add navigation handler for run clicks

### Phase 5: Polish and Testing

- [ ] Verify responsive layouts
- [ ] Test with various run counts (0, 1, many)
- [ ] Test navigation to research detail page
- [ ] Test status badge colors match research feature
- [ ] Update feature exports in `index.ts`

## File Structure (Proposed)

```
frontend/src/
  app/(dashboard)/
    conversations/
      page.tsx                              # NO CHANGE (uses existing components)

  features/conversation/
    components/
      IdeationQueueCard.tsx                 # MODIFY
      IdeationQueueRunItem.tsx              # NEW
      IdeationQueueRunsList.tsx             # NEW
    hooks/
      useConversationResearchRuns.ts        # NEW
    types/
      ideation-queue.types.ts               # MODIFY
    utils/
      ideation-queue-utils.tsx              # MODIFY
    index.ts                                # MODIFY
```

## UI Design Specifications

### Card with Runs Layout

```
+--------------------------------------------------------------------------------+
| [Status Badge]  | Title (truncated)                    | Created  | Updated    |
|                 | Abstract preview (line-clamp-2)...   |          |            |
|                 |                                      |          |            |
| ------------------- Research Runs ({count}) ------------------------------- |
| [expand/collapse toggle or always visible if count > 0]                        |
|                                                                                |
|   [Running]  rp-abc123...  | RTX A4000  | Started 2h ago    | [View ->]     |
|   [Completed] rp-def456... | RTX A5000  | 1 day ago         | [View ->]     |
|   [Failed]   rp-ghi789...  | RTX A4000  | 3 days ago        | [View ->]     |
+--------------------------------------------------------------------------------+
```

### Research Run Row

```
+----------------------------------------------------------------------+
| [Status]  rp-{truncated}  |  {gpu_type}  |  {relative_time}  | [->]  |
+----------------------------------------------------------------------+
```

### Status Badge Colors (consistent with research feature)

- Pending: `bg-amber-500/15 text-amber-400`
- Running: `bg-sky-500/15 text-sky-400` (with subtle pulse animation)
- Completed: `bg-emerald-500/15 text-emerald-400`
- Failed: `bg-red-500/15 text-red-400`

## API Considerations

### Existing Endpoints (No Backend Changes Required)

| Endpoint | Use Case |
|----------|----------|
| `GET /api/conversations` | List conversations (current, no runs) |
| `GET /api/conversations/{id}` | Get conversation with `research_runs` array |

### Response Structure (from `ConversationResponse`)

```typescript
interface ResearchRunSummary {
  run_id: string;
  status: string; // "pending" | "running" | "failed" | "completed"
  idea_id: number;
  idea_version_id: number;
  pod_id: string | null;
  pod_name: string | null;
  gpu_type: string | null;
  cost: number;
  public_ip: string | null;
  ssh_port: string | null;
  pod_host_id: string | null;
  error_message: string | null;
  last_heartbeat_at: string | null;
  heartbeat_failures: number;
  created_at: string;
  updated_at: string;
}
```

## Acceptance Criteria

1. [ ] Each idea card shows a count of research runs (e.g., "3 runs")
2. [ ] Users can view the list of research runs for each idea
3. [ ] Each research run displays: status badge, run ID, GPU type, created time
4. [ ] Status badges use consistent colors matching the Research tab
5. [ ] Clicking a research run navigates to `/research/{runId}`
6. [ ] Ideas with no runs show "No runs yet" message
7. [ ] Loading state shown while fetching runs
8. [ ] Error state handled gracefully
9. [ ] Responsive layout works on mobile and desktop
10. [ ] TypeScript compiles without errors
11. [ ] No console errors or warnings

## Out of Scope (Future Enhancements)

1. Real-time SSE updates for running research runs in the list
2. Bulk operations on research runs
3. Filtering ideas by run status
4. Run comparison features

## Related Documentation

- `.agent/Tasks/ideation-queue-enhancement/PRD.md` - Original ideation queue enhancement
- `.agent/System/frontend_architecture.md` - Feature-based architecture
- `.agent/SOP/frontend_api_hooks.md` - Creating API hooks
- `.agent/SOP/frontend_features.md` - Feature creation guidelines

## Progress Log

### 2025-12-05
- Created initial PRD based on user requirements
- Analyzed existing backend support (research_runs in ConversationResponse)
- Identified existing database method `list_research_runs_for_conversation`
- Determined no backend changes required - purely frontend enhancement
- Created 00-context.md breadcrumb
- Created implementation plan with 5 phases

### 2025-12-08
- Planning phase completed (01-planning.md)
- Reusable assets analysis completed (01a-reusable-assets.md) - identified 7 reusable assets
- Architecture design completed (02-architecture.md) - SOLID-compliant component design
- Next.js 15 guidance documented (02a-nextjs-guidance.md)
- Implementation completed (03-implementation.md):
  - Created useConversationResearchRuns hook
  - Created IdeationQueueRunItem component
  - Created IdeationQueueRunsList component
  - Modified IdeationQueueCard with expand/collapse
  - TypeScript compilation: PASS
- Copy review completed (03a-copy-review.md) - 5 fixes identified
- Documentation review completed (04-review.md):
  - Updated frontend_features.md with Expandable Card Pattern
  - Updated frontend_api_hooks.md with On-Demand Nested Data Fetching
  - Updated frontend_architecture.md with reusable research utilities
- Copy fixes applied (5 improvements for accessibility and clarity)
- Modified default state: Research runs now shown expanded by default (user request)
