# Auto Evaluation Details UI - Product Requirements Document

## Overview

**Feature Name:** Auto Evaluation Details UI
**Task ID:** auto-evaluation-details-ui
**Status:** See `task.json` for current status
**Created:** 2025-12-09

### Summary

Expose existing LLM review data from the `rp_llm_reviews` database table to the frontend via a modal dialog UI. The data already exists and is populated by the research pipeline during paper review generation. This feature creates the full data path from database to user interface.

---

## Problem Statement

When a research pipeline run completes, an LLM-based review is generated and stored in the database. Currently, users have no way to view this evaluation data through the UI. They need visibility into:

- The verdict (Accept/Reject mapped to PASS/FAIL)
- Quantitative scores across 9 metrics
- Qualitative analysis including summary, strengths, weaknesses, questions, limitations
- Whether ethical concerns were flagged

---

## User Requirements

### Primary User

Researchers monitoring their research pipeline runs who want to understand the automated evaluation of their generated papers.

### User Goals

1. **View evaluation verdict** - Quick pass/fail indication at a glance
2. **Analyze quantitative scores** - Understand how the paper performed across specific metrics
3. **Read qualitative feedback** - Access detailed analysis including strengths and improvement areas
4. **Filter view** - Toggle between scores only, analysis only, or combined view

### User Flow

1. User navigates to Research Run Detail page (`/research/[runId]`)
2. User clicks "View Auto Evaluation" button (visible only when review data exists)
3. Modal opens displaying evaluation details
4. User can switch between tabs (Both, Scores, Analysis)
5. User can expand/collapse qualitative sections
6. User closes modal to return to run details

---

## Functional Requirements

### Backend Requirements

#### FR-1: Database Mixin
- Create `RpLlmReviewsMixin` class in `server/app/services/database/rp_llm_reviews.py`
- Implement `get_llm_review_by_run_id(run_id: str) -> Optional[LlmReview]` method
- Return `None` if no review exists for the run

#### FR-2: Pydantic Model
- Create `LlmReviewResponse` model in `server/app/models/research_pipeline.py`
- Fields must match database schema:
  - `id`: int
  - `run_id`: str
  - `summary`: str
  - `strengths`: List[str] (JSONB array)
  - `weaknesses`: List[str] (JSONB array)
  - `originality`: float (Decimal converted)
  - `quality`: float
  - `clarity`: float
  - `significance`: float
  - `soundness`: float
  - `presentation`: float
  - `contribution`: float
  - `overall`: float (1-10 scale)
  - `confidence`: float (1-5 scale)
  - `questions`: List[str] (JSONB array)
  - `limitations`: List[str] (JSONB array)
  - `ethical_concerns`: bool
  - `decision`: str ("Accept" or "Reject")
  - `source_path`: Optional[str]
  - `created_at`: str (ISO timestamp)

#### FR-3: API Endpoint
- Add GET endpoint: `/api/conversations/{conversation_id}/idea/research-run/{run_id}/review`
- Reuse existing auth and ownership validation from `research_pipeline_runs.py`
- Return 404 if review not found
- Return `LlmReviewResponse` on success

### Frontend Requirements

#### FR-4: TypeScript Types
- Add `LlmReview` interface to `frontend/src/types/research.ts`
- Match backend model structure (snake_case for API compatibility)

#### FR-5: React Hook
- Create `useReviewData(runId: string, conversationId: number, enabled: boolean)` hook
- Use React Query with lazy loading pattern
- Return `{ review, isLoading, error, refetch }`
- 30-second stale time for caching

#### FR-6: Modal Component
- Create `ReviewModal.tsx` following `PromptEditModal.tsx` pattern
- Props: `isOpen: boolean`, `onClose: () => void`, `runId: string`, `conversationId: number`
- Use `createPortal` for DOM rendering
- Handle loading, error, and empty states

#### FR-7: Verdict Header
- Create `ReviewHeader.tsx` component
- Display PASS badge (green) for "Accept" decision
- Display FAIL badge (red) for "Reject" decision
- Show modal title "Auto Evaluation Details"

#### FR-8: Tab Navigation
- Create `ReviewTabs.tsx` component
- Three tabs: "Both", "Scores", "Analysis"
- Default to "Both" tab
- Tab state managed in `ReviewModal`

#### FR-9: Quantitative Scores Grid
- Create `ReviewScores.tsx` component
- Display 9 metric cards in responsive grid
- Show score as fraction (e.g., "3/4")
- Metrics and their max values:
  - Originality: /4
  - Quality: /4
  - Clarity: /4
  - Significance: /4
  - Soundness: /4
  - Presentation: /4
  - Contribution: /4
  - Overall: /10
  - Confidence: /5

#### FR-10: Qualitative Analysis
- Create `ReviewAnalysis.tsx` component
- Expandable sections with chevron icons
- Sections:
  - Summary (text, expanded by default)
  - Strengths (bullet list, green styling, expanded by default)
  - Weaknesses (bullet list, amber styling, collapsed by default)
  - Questions (bullet list, sky styling, collapsed, hidden if empty)
  - Limitations (bullet list, gray styling, collapsed, hidden if empty)
  - Ethical Concerns banner (conditional, red styling if true)

#### FR-11: Page Integration
- Add "View Auto Evaluation" button to research run detail page
- Button visible only when `status === "completed"`
- Lazy load review data when modal opens

---

## Technical Design

### Architecture Approach

**Selected: Feature-Slice Pattern**

Components colocated within the existing research feature structure:
```
frontend/src/features/research/
  hooks/
    useReviewData.ts
  components/
    run-detail/
      review/
        ReviewModal.tsx
        ReviewHeader.tsx
        ReviewTabs.tsx
        ReviewScores.tsx
        ReviewAnalysis.tsx
```

### Data Flow

```
[User clicks button]
       |
       v
[Modal opens, useReviewData enabled]
       |
       v
[React Query fetches from API]
       |
       v
[GET /conversations/{id}/idea/research-run/{run_id}/review]
       |
       v
[FastAPI endpoint validates auth/ownership]
       |
       v
[Database mixin queries rp_llm_reviews table]
       |
       v
[Response returned through chain]
       |
       v
[Modal renders review data]
```

### Database Schema Reference

```sql
-- From migration 0010_create_rp_llm_reviews.py
CREATE TABLE rp_llm_reviews (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES research_pipeline_runs(run_id) ON DELETE CASCADE,
    summary         TEXT NOT NULL,
    strengths       JSONB NOT NULL DEFAULT '[]'::jsonb,
    weaknesses      JSONB NOT NULL DEFAULT '[]'::jsonb,
    originality     NUMERIC(5,2) NOT NULL,
    quality         NUMERIC(5,2) NOT NULL,
    clarity         NUMERIC(5,2) NOT NULL,
    significance    NUMERIC(5,2) NOT NULL,
    questions       JSONB NOT NULL DEFAULT '[]'::jsonb,
    limitations     JSONB NOT NULL DEFAULT '[]'::jsonb,
    ethical_concerns BOOLEAN NOT NULL DEFAULT FALSE,
    soundness       NUMERIC(5,2) NOT NULL,
    presentation    NUMERIC(5,2) NOT NULL,
    contribution    NUMERIC(5,2) NOT NULL,
    overall         NUMERIC(5,2) NOT NULL,
    confidence      NUMERIC(5,2) NOT NULL,
    decision        TEXT NOT NULL,
    source_path     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rp_llm_reviews_run_id ON rp_llm_reviews(run_id);
```

---

## UI Design Specifications

### Modal Layout

```
+--------------------------------------------------+
| Auto Evaluation Details                    [X]   |
|--------------------------------------------------|
| [PASS/FAIL Badge]                                |
|--------------------------------------------------|
| [Both] [Scores] [Analysis]                       |
|--------------------------------------------------|
|                                                  |
| Quantitative Scores                              |
| +------+ +------+ +------+                       |
| | 3/4  | | 3/4  | | 4/4  |  ...                  |
| | Orig | | Qual | | Clar |                       |
| +------+ +------+ +------+                       |
|                                                  |
| Qualitative Analysis                             |
| v Summary                                        |
|   [Summary text...]                              |
|                                                  |
| v Strengths                                      |
|   - Strength 1                                   |
|   - Strength 2                                   |
|                                                  |
| > Weaknesses (collapsed)                         |
| > Questions (if any)                             |
| > Limitations (if any)                           |
|                                                  |
| [!] Ethical concerns flagged (if true)           |
|                                                  |
+--------------------------------------------------+
```

### Color Tokens (from design-guidelines.md)

| Element | Light Mode | Dark Mode |
|---------|------------|-----------|
| PASS Badge | bg-green-100 text-green-800 | bg-green-500/15 text-green-400 |
| FAIL Badge | bg-red-100 text-red-800 | bg-red-500/15 text-red-400 |
| Strengths | text-green-600 | text-green-400 |
| Weaknesses | text-amber-600 | text-amber-400 |
| Questions | text-sky-600 | text-sky-400 |
| Limitations | text-slate-600 | text-slate-400 |
| Ethical Banner | bg-red-50 text-red-700 | bg-red-500/10 text-red-400 |

### Tab Styling

```typescript
const TAB_CONFIG = {
  both: { label: "Both", activeClass: "bg-primary/15 text-primary" },
  scores: { label: "Scores", activeClass: "bg-sky-500/15 text-sky-400" },
  analysis: { label: "Analysis", activeClass: "bg-emerald-500/15 text-emerald-400" },
};
```

---

## Implementation Plan

### Phase 1: Backend (Estimated: 2-3 hours)

1. **Create database mixin** (`rp_llm_reviews.py`)
   - Define `LlmReview` NamedTuple for internal use
   - Implement `get_llm_review_by_run_id()` method
   - Handle Decimal to float conversion

2. **Update database __init__.py**
   - Import `RpLlmReviewsMixin`
   - Add to `DatabaseManager` inheritance chain

3. **Add Pydantic model** (`research_pipeline.py`)
   - Define `LlmReviewResponse` model
   - Export from `models/__init__.py`

4. **Add API endpoint** (`research_pipeline_runs.py`)
   - GET endpoint with auth validation
   - Convert database result to response model

### Phase 2: Frontend Types & Hook (Estimated: 1-2 hours)

5. **Add TypeScript types** (`research.ts`)
   - `LlmReview` interface
   - `LlmReviewApi` for API response (if needed)

6. **Create React hook** (`useReviewData.ts`)
   - React Query implementation
   - Lazy loading pattern with `enabled` prop

### Phase 3: UI Components (Estimated: 3-4 hours)

7. **Create ReviewModal.tsx**
   - Portal-based modal structure
   - State management for tabs
   - Loading/error states

8. **Create ReviewHeader.tsx**
   - Verdict badge logic
   - Title display

9. **Create ReviewTabs.tsx**
   - Tab navigation UI
   - Active state styling

10. **Create ReviewScores.tsx**
    - Score grid layout
    - Fraction formatting

11. **Create ReviewAnalysis.tsx**
    - Collapsible sections
    - Conditional rendering
    - Bullet lists

### Phase 4: Integration (Estimated: 1-2 hours)

12. **Update run-detail/index.ts**
    - Export new components

13. **Update research run page**
    - Add trigger button
    - Wire up modal state

---

## Error Handling

### Backend Errors
- 400: Invalid conversation_id (must be positive)
- 403: User does not own conversation
- 404: Conversation, run, or review not found
- 500: Database query errors (logged, generic message returned)

### Frontend Errors
- Network error: Show retry button in modal
- 404: Show "No evaluation available" message
- Other errors: Show error message with close option

---

## Testing Considerations

### Backend Tests
- Unit test for mixin query method
- Integration test for API endpoint
- Test 404 case when review doesn't exist

### Frontend Tests
- Component rendering tests for each new component
- Hook loading/error state tests
- Modal open/close behavior tests
- Tab switching tests

---

## Dependencies

### Existing Code to Reuse
- `PromptEditModal.tsx` - Modal pattern reference
- `research_pipeline_runs.py` - Auth validation pattern
- `ResearchPipelineRunsMixin` - Database mixin pattern
- `apiFetch` - API client
- `useQuery` - React Query hook

### No New Dependencies Required
- All UI components built with existing Tailwind utilities
- No additional npm packages needed

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| `.agent/System/server_architecture.md` | Backend patterns |
| `.agent/System/frontend_architecture.md` | Frontend patterns |
| `.agent/System/design-guidelines.md` | UI design tokens |
| `.agent/SOP/server_services.md` | Database mixin pattern |
| `.agent/SOP/frontend_api_hooks.md` | React Query patterns |
| `server/database_migrations/versions/0010_create_rp_llm_reviews.py` | Schema reference |

---

## Open Questions

1. **Score scale confirmation**: Verify that metrics 1-4 scale is correct (not 1-5). Need to check how `perform_llm_review.py` generates scores.

2. **Multiple reviews**: Can a single run have multiple reviews? Current design assumes 1:1 relationship. If multiple, need to decide which to show (latest? all?).

3. **Button placement**: Where exactly on the run detail page should the "View Auto Evaluation" button appear? Suggest near the status/header area.

---

## Approval Checklist

Before proceeding to implementation:

- [ ] Confirm score scales are accurate
- [ ] Confirm single review per run assumption
- [ ] Approve component structure in `run-detail/review/`
- [ ] Approve modal vs inline expansion approach
- [ ] Approve PASS/FAIL terminology mapping
