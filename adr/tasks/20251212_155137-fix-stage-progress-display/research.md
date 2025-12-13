## Research: Fix Misleading Progress Percentage Display in Pipeline Stages

### Summary
The StageInfo interface has been partially updated with iteration/maxIterations fields, but getStageInfo() return statements haven't populated these fields yet. The render logic at lines 348-353 currently shows percentage for all stages. Implementation requires: (1) populating iteration/maxIterations from StageProgress.details in getStageInfo(), (2) creating STEP_LABELS mapping for Stage 5, (3) updating render logic to conditionally display iteration-based text for Stages 1-4 and step name + percentage for Stage 5.

### Code Paths

| File | Lines | Purpose | Action |
|------|-------|---------|--------|
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 83-92 | StageInfo interface with iteration/maxIterations fields | reference |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 249-325 | getStageInfo() function - needs to populate iteration/maxIterations | modify |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 348-353 | Stage header render logic - needs conditional display | modify |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 204-210 | PAPER_GENERATION_STEPS constant (existing) | reference |
| `frontend/src/features/research/components/run-detail/paper-generation-progress.tsx` | 11-16 | STEP_LABELS mapping pattern for Stage 5 | reference |
| `frontend/src/types/research.ts` | 174-186 | StageProgress type with iteration/max_iterations | reference |

### Data Flow
`StageProgress.iteration` (line 176) + `StageProgress.max_iterations` (line 177) → `getStageInfo()` (lines 249-325) → `StageInfo.iteration` (line 86) + `StageInfo.maxIterations` (line 88) → Stage header render (lines 348-353)

### Implementation Details

#### 1. StageInfo Interface (Lines 83-92) - ALREADY UPDATED
```typescript
interface StageInfo {
  status: "pending" | "in_progress" | "completed";
  /** For Stages 1-4: current iteration (1-based) */
  iteration: number | null;  // ✅ Already added
  /** For Stages 1-4: max iterations (budget) */
  maxIterations: number | null;  // ✅ Already added
  /** For Stage 5 only: step-based progress percent */
  progressPercent: number | null;
  details: StageProgress | null;
}
```

#### 2. getStageInfo() Function - NEEDS UPDATE

**Lines 251-281: Stage 5 (paper_generation) branch**
- Currently returns: `{ status, progressPercent, details: null }`
- **Action**: Add `iteration: null, maxIterations: null` to all return statements

**Lines 283-325: Stages 1-4 branch**
- Line 300: `latestProgress` available with iteration/max_iterations data
- Currently returns: `{ status, progressPercent, details: latestProgress }`
- **Action**: Extract and return:
  - `iteration: latestProgress.iteration`
  - `maxIterations: latestProgress.max_iterations`
  - Keep `progressPercent` for Stage 5 compatibility

**Specific return statement locations:**
- Line 256-257: pending state for Stage 5
- Line 263-266: pending state fallback for Stage 5
- Line 277-280: active/completed state for Stage 5
- Line 292-296: pending state for Stages 1-4
- Line 302-306: pending state fallback for Stages 1-4
- Line 320-324: active/completed state for Stages 1-4

#### 3. Step Labels Mapping - NEEDS CREATION

**Action**: Add STEP_LABELS constant after PAPER_GENERATION_STEPS (after line 210)
```typescript
const STEP_LABELS: Record<string, string> = {
  plot_aggregation: "Plot Aggregation",
  citation_gathering: "Citation Gathering",
  paper_writeup: "Paper Writeup",
  paper_review: "Paper Review",
};
```

**Reference**: Pattern exists in `paper-generation-progress.tsx:11-16`

#### 4. Stage Header Render Logic - NEEDS UPDATE

**Current code (lines 348-353):**
```tsx
<h3 className="text-base font-semibold text-white">
  Stage {stage.id}: {stage.title}
  {info.status !== "pending" && (
    <span className="ml-2 text-slate-400">({info.progressPercent}%)</span>
  )}
</h3>
```

**Required changes:**
- Line 333: `info` already available from `getStageInfo(stage.key)`
- Line 334: `isPaperGeneration` already computed
- Line 221-222: `latestEvent` for paper generation available from `paperGenerationProgress[paperGenerationProgress.length - 1]`

**New logic structure:**
1. For Stages 1-4 in_progress: Show "— Iteration X of Y"
2. For Stages 1-4 completed: Show "— Completed in X iterations"
3. For Stage 5 (any non-pending): Show "— {step_name} ({percent}%)"

**Step name access**: `latestEvent?.step` → `STEP_LABELS[latestEvent.step]`

### Patterns Applied
- Derived state over synchronized state (React 19 SSR pattern)
- Use @/ imports for internal modules (frontend path mapping)
- Type safety with null checks for optional fields

### Constraints
- Must not use useState + useEffect for SSR guards (ADR: 20251212_120946-react-19-ssr-patterns.md:40)
- Must use @/ imports (ADR: 20251212_152505-frontend-path-mapping-pattern.md:156)
- StageProgress type uses snake_case for SSE compatibility (types/research.ts:154 comment)
- iteration is 1-based (not 0-based)

### Integration Points
- StageProgress events from SSE → useResearchRunDetails → stageProgress array → getStageInfo()
- PaperGenerationEvent from SSE → paperGenerationProgress array → latestEvent.step
- PAPER_GENERATION_STEPS constant used for segment generation, STEP_LABELS needed for display

### Edge Cases
- pending state: iteration/maxIterations should be null
- Stage 5: iteration/maxIterations should always be null (step-based, not iteration-based)
- Null safety: info.iteration !== null before rendering iteration text
- latestEvent?.step existence check before accessing STEP_LABELS
