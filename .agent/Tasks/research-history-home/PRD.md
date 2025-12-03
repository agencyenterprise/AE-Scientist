# Research History on Home Page - Product Requirements Document

## Overview
Add a "Research History" section to the home page that displays the user's 10 most recent research runs. This provides quick visibility into ongoing and past research directly from the main dashboard, allowing users to track their research activity and quickly re-engage with previous work.

## Status
- [x] Planning
- [x] Architecture
- [x] Implementation
- [x] Testing (partial - manual verification)
- [x] Documentation Review
- [ ] Complete (pending approval)

## User Stories

### Primary User Stories
1. **As a researcher**, I want to see my recent research history on the home page so that I can quickly track my ongoing experiments without navigating away.

2. **As a researcher**, I want to see the status of each research run (Pending, Running, Completed, Failed) so that I know which experiments need attention.

3. **As a researcher**, I want to see when each research was started so that I can understand my research timeline.

4. **As a researcher**, I want to quickly navigate to a research run to see more details or relaunch an experiment.

### Secondary User Stories
4. **As a new user**, I want to see an empty state message when I have no research history so that I understand how to get started.

## Requirements

### Functional Requirements
1. Display the 10 most recent research runs for the current authenticated user
2. Show research runs in reverse chronological order (newest first)
3. Each research entry must display:
   - Research title (from `ideaTitle`)
   - Status badge with appropriate color coding:
     - Pending (amber)
     - Running (sky blue, with spinner)
     - Completed (emerald green)
     - Failed (red)
   - Timestamp showing relative time (e.g., "2 hours ago")
   - Research hypothesis/description (truncated if needed)
   - "Relaunch" action button linking to the conversation page
4. Section appears below the "Create Hypothesis" form card
5. Use terminology "Research" not "Hypothesis" throughout
6. Show empty state when user has no research history
7. Show loading skeleton while fetching data

### Non-Functional Requirements
1. **Performance**: Data should load within 1 second on typical connection
2. **Responsiveness**: Layout should adapt gracefully on mobile devices
3. **Consistency**: Visual style must match existing dashboard components
4. **Accessibility**: Status badges should have accessible text for screen readers

## Technical Decisions

### Based on project documentation:
- **Pattern**: Feature-based component with dedicated hook (per frontend_architecture.md)
- **SOP**: Follow frontend_features.md for component organization
- **Dependencies**:
  - Existing `/api/research-runs/` endpoint (no backend changes needed)
  - Existing `ResearchRun` type
  - Existing API adapter functions

### Component Architecture
```
features/research/
├── components/
│   ├── ResearchHistoryList.tsx      # NEW - Compact list for home page
│   ├── ResearchHistoryCard.tsx      # NEW - Individual research card
│   ├── ResearchHistoryEmpty.tsx     # NEW - Empty state component
│   └── ResearchHistorySkeleton.tsx  # NEW - Loading skeleton
├── hooks/
│   └── useRecentResearch.ts         # NEW - Fetch last 10 runs
└── utils/
    └── research-utils.ts            # NEW - Extract shared utilities
```

## Reusability Analysis

### Existing Assets to REUSE
- [x] `getStatusBadge()` function - extract from `ResearchBoardTable.tsx`
- [x] `formatRelativeTime()` function - extract from `ResearchBoardTable.tsx`
- [x] `convertApiResearchRunList` from `@/shared/lib/api-adapters`
- [x] `apiFetch` from `@/shared/lib/api-client`
- [x] `ResearchRun`, `ResearchRunListResponseApi` types from `@/types/research`
- [x] Lucide icons: `CheckCircle2`, `Clock`, `Loader2`, `AlertCircle`, `RotateCcw`

### Similar Features to Reference
- `ResearchBoardTable.tsx`: Status badges, card structure, time formatting
- `CreateHypothesisForm.tsx`: Pattern for integrating feature component into home page

### Code to Extract/Refactor
The following functions should be extracted from `ResearchBoardTable.tsx` to a shared utility file for reuse:
- `getStatusBadge(status: string): ReactNode`
- `formatRelativeTime(dateString: string): string`

### Needs Codebase Analysis
- [x] No - Simple feature with well-understood patterns

## Implementation Plan

### Phase 1: Utility Extraction
- [x] Create `shared/lib/date-utils.ts` with `formatRelativeTime`
- [x] Create `features/research/utils/research-utils.tsx` with `getStatusBadge`
- [x] Update `ResearchBoardTable.tsx` to import from utils
- [x] Verify existing research page still works

### Phase 2: Hook Implementation
- [x] Create `features/research/hooks/useRecentResearch.ts`
- [x] Implement hook that fetches `/api/research-runs/?limit=10`
- [x] Return `{ researchRuns, isLoading, error, refetch }`
- [x] Add error handling

### Phase 3: Component Implementation
- [x] Create `ResearchHistorySkeleton.tsx` - loading state
- [x] Create `ResearchHistoryEmpty.tsx` - empty state
- [x] Create `ResearchHistoryCard.tsx` - individual research card
- [x] Create `ResearchHistoryList.tsx` - container component

### Phase 4: Home Page Integration
- [x] Update `/app/(dashboard)/page.tsx` to include `ResearchHistoryList`
- [x] Position below the "Create Hypothesis" form card
- [x] Add section heading "Your Recent Research"

### Phase 5: Testing & Polish
- [ ] Test with 0 research runs (empty state)
- [ ] Test with 1-10 research runs
- [ ] Test with various statuses
- [ ] Test loading state
- [ ] Test error state
- [ ] Verify mobile responsiveness

## File Structure (Final)

```
frontend/src/
├── app/(dashboard)/
│   └── page.tsx                    # MODIFY - Add ResearchHistoryList
│
├── shared/lib/
│   └── date-utils.ts               # NEW - Shared date formatting
│
└── features/research/
    ├── components/
    │   ├── ResearchBoardTable.tsx      # MODIFY - Import from utils
    │   ├── ResearchHistoryList.tsx     # NEW
    │   ├── ResearchHistoryCard.tsx     # NEW
    │   ├── ResearchHistoryEmpty.tsx    # NEW
    │   └── ResearchHistorySkeleton.tsx # NEW
    ├── hooks/
    │   ├── useResearchRunSSE.ts        # EXISTING
    │   └── useRecentResearch.ts        # NEW
    └── utils/
        └── research-utils.ts           # NEW (extracted from ResearchBoardTable)
```

## UI Design Specifications

### ResearchHistoryList Container
```
Section Header: "Your Recent Research" (text-xl font-semibold text-white)
Container: rounded-xl border border-slate-800/70 bg-slate-950/80 p-4
Max-width: max-w-3xl (same as form container)
```

### ResearchHistoryCard Layout
```
┌────────────────────────────────────────────────────────────────┐
│ [Status Badge]                                    [Timestamp]  │
│ Research Title (font-semibold text-white)                      │
│ Hypothesis description (text-sm text-slate-400 line-clamp-2)   │
│                                              [Relaunch Button] │
└────────────────────────────────────────────────────────────────┘
```

### Status Badge Colors (from existing)
- Pending: `bg-amber-500/15 text-amber-400`
- Running: `bg-sky-500/15 text-sky-400` (with spinning icon)
- Completed: `bg-emerald-500/15 text-emerald-400`
- Failed: `bg-red-500/15 text-red-400`

### Empty State
```
┌────────────────────────────────────────────────────────────────┐
│                    [Beaker/Flask Icon]                         │
│               No research history yet                          │
│    Submit your first hypothesis above to get started           │
└────────────────────────────────────────────────────────────────┘
```

## API Contract

### Endpoint (Existing)
```
GET /api/research-runs/?limit=10
```

### Response Format (Existing)
```json
{
  "items": [
    {
      "run_id": "abc123",
      "status": "running",
      "idea_title": "Neural Network Optimization",
      "idea_hypothesis": "Applying gradient clipping...",
      "current_stage": "baseline",
      "progress": 0.35,
      "gpu_type": "A100",
      "best_metric": null,
      "created_by_name": "John Doe",
      "created_at": "2025-12-03T10:00:00Z",
      "updated_at": "2025-12-03T10:30:00Z",
      "artifacts_count": 0,
      "error_message": null,
      "conversation_id": 42
    }
  ],
  "total": 25
}
```

## Acceptance Criteria

1. [ ] Research history section appears on home page below the hypothesis form
2. [ ] Shows up to 10 most recent research runs for current user
3. [ ] Each card displays: title, status badge, timestamp, hypothesis snippet
4. [ ] Status badges match the color scheme of existing research board
5. [ ] "Relaunch" button navigates to `/conversations/{conversationId}`
6. [ ] Empty state shows when user has no research history
7. [ ] Loading skeleton appears while data is fetching
8. [ ] Section uses "Research" terminology (not "Hypothesis")
9. [ ] Mobile responsive layout
10. [ ] No console errors or warnings

## Related Documentation
- `.agent/System/frontend_architecture.md` - Feature-based architecture patterns
- `.agent/SOP/frontend_features.md` - Feature creation guidelines
- `.agent/SOP/frontend_api_hooks.md` - API hook patterns
- `.agent/Tasks/research-history-home/02-architecture.md` - Detailed architecture

## Progress Log

### 2025-12-03
- Created initial PRD based on feature request
- Analyzed existing codebase for reusable components
- Identified that backend API already supports this feature
- Determined minimal implementation approach with maximum reuse
- Created planning breadcrumb (01-planning.md)
- Created reusable assets inventory (01a-reusable-assets.md)
- **Completed architecture phase (02-architecture.md)**
- **Implementation completed:**
  - Extracted `formatRelativeTime` to `shared/lib/date-utils.ts`
  - Extracted `getStatusBadge` to `features/research/utils/research-utils.tsx`
  - Updated `ResearchBoardTable.tsx` to import from extracted utilities
  - Created `useRecentResearch` hook using React Query
  - Created `ResearchHistorySkeleton`, `ResearchHistoryEmpty`, `ResearchHistoryCard`, `ResearchHistoryList` components
  - Integrated `ResearchHistoryList` into home page
  - TypeScript and ESLint checks passed
- **Documentation review completed (04-review.md):**
  - Updated `.agent/SOP/frontend_api_hooks.md` with React Query priority guidance
  - Updated `.agent/System/frontend_architecture.md` with new shared utilities and research feature
  - Updated `.agent/SOP/frontend_features.md` with research feature entry
  - Pending user approval to mark complete
