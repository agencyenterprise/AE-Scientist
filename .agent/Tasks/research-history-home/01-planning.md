# Planning Phase

## Agent
feature-planner

## Timestamp
2025-12-03 10:30

## Input Received
- Context: `.agent/Tasks/research-history-home/00-context.md`
- Project docs consulted:
    - `.agent/README.md`
    - `.agent/System/project_architecture.md`
    - `.agent/System/frontend_architecture.md`
    - `.agent/System/server_architecture.md`

## Documentation Research Summary

### Project Structure Understanding
The project follows a feature-based architecture:
- **Frontend**: Next.js 15 with React 19, using App Router
- **Backend**: FastAPI with PostgreSQL
- **Styling**: Tailwind CSS with shadcn/ui components
- **State**: React Context for feature-level state, React Query for server state

### Existing Feature Analysis

#### Research Feature (`/frontend/src/features/research/`)
Already contains:
- `ResearchContext.tsx` - Context for research run state management
- `ResearchBoardTable.tsx` - Card-based display of research runs (full-featured)
- `ResearchBoardHeader.tsx` - Filtering and search header
- `useResearchRunSSE.ts` - SSE hook for real-time updates

#### Research API (`/server/app/api/research_runs.py`)
Existing endpoint: `GET /api/research-runs/`
- Supports `limit`, `offset`, `search`, `status` query params
- Returns `ResearchRunListResponse` with `items` and `total`
- Already filters by user_id (current authenticated user)

#### Key Types (`/frontend/src/types/research.ts`)
```typescript
interface ResearchRun {
  runId: string;
  status: string;
  ideaTitle: string;
  ideaHypothesis: string | null;
  currentStage: string | null;
  progress: number | null;
  gpuType: string | null;
  bestMetric: string | null;
  createdByName: string;
  createdAt: string;
  updatedAt: string;
  artifactsCount: number;
  errorMessage: string | null;
  conversationId: number;
}
```

## Reasoning

### Why This Approach

The feature request is well-suited for **maximum reuse** because:

1. **Backend API is complete** - The `/api/research-runs/` endpoint already supports all required functionality (user filtering, pagination, status). We just need to call it with `limit=10`.

2. **Types are defined** - `ResearchRun` type has all fields needed: title, status, timestamp (createdAt), hypothesis (ideaHypothesis).

3. **Similar UI exists** - `ResearchBoardTable.tsx` shows cards with status badges, timestamps, and action buttons. We can create a simplified "compact" variant.

### Design Decision: New Compact Component vs Reusing Existing

**Decision**: Create a new compact `ResearchHistoryCard` component

**Rationale**:
- The existing `ResearchBoardTable` is full-featured (shows GPU, metrics, progress bars, artifacts)
- Home page needs a simpler, more condensed view
- Different action button: "Relaunch experiment" vs "View Details"
- Different layout: vertical list vs full card grid

However, we WILL reuse:
- Status badge rendering logic from `ResearchBoardTable.tsx`
- `formatRelativeTime` utility from existing component
- `ResearchRun` type and API adapters

### Pattern Selection
- **Pattern**: Feature-based component with dedicated hook
- **Because**: Follows existing architecture, keeps home page thin
- **Reference**: Similar to how `CreateHypothesisForm` is a feature component used in home page

### Dependencies Identified
- `@/shared/lib/api-adapters` - for `convertApiResearchRunList`
- `@/shared/lib/api-client` - for `apiFetch`
- `@/types/research` - for types
- `lucide-react` - for icons
- `date-fns` - for `formatDistanceToNow`

### Risks & Considerations
- **Risk 1**: Home page is server component, needs "use client" for data fetching
  - **Mitigation**: Wrap in client component, similar to how `CreateHypothesisForm` works
- **Risk 2**: "Relaunch experiment" action needs clarification
  - **Mitigation**: Initially link to conversation page where user can re-run; document for future enhancement

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Create new component vs extend existing | New `ResearchHistoryList` | Existing component is too feature-rich for home page |
| Data fetching strategy | Custom hook `useRecentResearch` | Simple, focused, no context needed |
| Relaunch action | Link to `/conversations/{id}` | Keeps scope manageable, allows re-ideation |
| Location | `features/research/components/` | Extends existing research feature |
| Terminology | "Research" not "Hypothesis" | Per request, update all copy |

## Reusability Analysis

### Existing Assets to REUSE
- [x] `getStatusBadge()` function from `ResearchBoardTable.tsx`
- [x] `formatRelativeTime()` function from `ResearchBoardTable.tsx`
- [x] `convertApiResearchRunList` from `api-adapters.ts`
- [x] `apiFetch` from `api-client.ts`
- [x] `ResearchRun` type from `types/research.ts`
- [x] Lucide icons (CheckCircle2, Clock, Loader2, AlertCircle, RotateCcw)

### Similar Features to Reference
- `ResearchBoardTable.tsx`: Status badges, card structure, time formatting
- `CreateHypothesisForm.tsx`: How to integrate a feature component into home page

### Needs Codebase Analysis
- [x] No - Simple feature with well-understood patterns

## Output Summary
- PRD created: `.agent/Tasks/research-history-home/PRD.md`
- Files to create: 3 frontend files (1 hook, 1 component, update 1 page)
- Estimated complexity: Low-Medium

## For Next Phase (Architecture)
Key considerations for the architect:
- Reuse `getStatusBadge` and `formatRelativeTime` - consider extracting to shared utils
- Keep component focused: no filtering/search, just last 10 runs
- Consider empty state when user has no research history
- Consider loading skeleton for better UX

## Approval Status
- [ ] Pending approval
- [ ] Approved - proceed to Architecture
- [ ] Modified - see feedback below

### Feedback (if modified)
{User feedback will be added here}
