# Implementation Plan: Fix Misleading Progress Percentage Display in Pipeline Stages

**Created**: 2025-12-12
**Based on**: research.md, ux-strategy.md, decision-brief.md
**Estimated changes**: 1 file, 4 modification areas

## Overview

Replace misleading percentage display with unified iteration/step-based counts across all stages:

- **Stages 1-4**: "Iteration X of Y" (in progress) / "Completed in X iterations" (done)
- **Stage 5**: "Step Name (Step X of 4)" (in progress) / "Completed in 4 steps" (done)

This involves: (1) adding a STEP_LABELS constant, (2) updating all 6 getStageInfo() return statements to include iteration/maxIterations fields, and (3) updating the stage header render logic for conditional display.

## Prerequisites

- [ ] None - all dependencies already exist in the codebase

---

## Step 1: Add STEP_LABELS Constant for Stage 5 Step Name Display

### File: `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx`

**Action**: Modify
**Lines**: 210-211 (insert after line 210)

#### Current Code (lines 204-211):

```typescript
// Paper generation step labels for Stage 5
const PAPER_GENERATION_STEPS = [
  { key: "plot_aggregation", label: "Plot Aggregation" },
  { key: "citation_gathering", label: "Citation Gathering" },
  { key: "paper_writeup", label: "Paper Writeup" },
  { key: "paper_review", label: "Paper Review" },
] as const;
```

#### Target Code:

```typescript
// Paper generation step labels for Stage 5
const PAPER_GENERATION_STEPS = [
  { key: "plot_aggregation", label: "Plot Aggregation" },
  { key: "citation_gathering", label: "Citation Gathering" },
  { key: "paper_writeup", label: "Paper Writeup" },
  { key: "paper_review", label: "Paper Review" },
] as const;

// Step key to display name mapping for Stage 5 header
const STEP_LABELS: Record<string, string> = {
  plot_aggregation: "Plot Aggregation",
  citation_gathering: "Citation Gathering",
  paper_writeup: "Paper Writeup",
  paper_review: "Paper Review",
};
```

#### Why

Stage 5 header needs to display the current step name (e.g., "Citation Gathering") alongside the percentage. This mapping converts the snake_case step keys from the backend to human-readable labels.

---

## Step 2: Update getStageInfo() Return Statements for Stage 5 (Paper Generation)

### File: `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx`

**Action**: Modify
**Lines**: 252-281

#### Current Code (lines 252-281):

```typescript
if (stageKey === "paper_generation") {
  if (paperGenerationProgress.length === 0) {
    return {
      status: "pending",
      progressPercent: 0,
      details: null,
    };
  }

  const latestEvent =
    paperGenerationProgress[paperGenerationProgress.length - 1];
  if (!latestEvent) {
    return {
      status: "pending",
      progressPercent: 0,
      details: null,
    };
  }
  const progressPercent = Math.round(latestEvent.progress * 100);

  let status: "pending" | "in_progress" | "completed";
  if (latestEvent.progress >= 1.0) {
    status = "completed";
  } else {
    status = "in_progress";
  }

  return {
    status,
    progressPercent,
    details: null, // Paper generation doesn't use StageProgress type
  };
}
```

#### Target Code:

```typescript
if (stageKey === "paper_generation") {
  if (paperGenerationProgress.length === 0) {
    return {
      status: "pending",
      iteration: null,
      maxIterations: null,
      progressPercent: 0,
      details: null,
    };
  }

  const latestEvent =
    paperGenerationProgress[paperGenerationProgress.length - 1];
  if (!latestEvent) {
    return {
      status: "pending",
      iteration: null,
      maxIterations: null,
      progressPercent: 0,
      details: null,
    };
  }
  const progressPercent = Math.round(latestEvent.progress * 100);

  let status: "pending" | "in_progress" | "completed";
  if (latestEvent.progress >= 1.0) {
    status = "completed";
  } else {
    status = "in_progress";
  }

  return {
    status,
    iteration: null,
    maxIterations: null,
    progressPercent,
    details: null, // Paper generation doesn't use StageProgress type
  };
}
```

#### Why

Stage 5 is step-based (not iteration-based), so iteration/maxIterations should always be null. This satisfies the StageInfo interface which requires these fields.

---

## Step 3: Update getStageInfo() Return Statements for Stages 1-4

### File: `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx`

**Action**: Modify
**Lines**: 291-324

#### Current Code (lines 291-324):

```typescript
// No progress data yet for this stage
if (stageProgresses.length === 0) {
  return {
    status: "pending",
    progressPercent: 0,
    details: null,
  };
}

// Use the most recent progress event (array is ordered by created_at)
const latestProgress = stageProgresses[stageProgresses.length - 1];
if (!latestProgress) {
  return {
    status: "pending",
    progressPercent: 0,
    details: null,
  };
}
const progressPercent = Math.round(latestProgress.progress * 100);

// Determine status based on progress value
let status: "pending" | "in_progress" | "completed";
if (latestProgress.progress >= 1.0) {
  status = "completed";
} else if (latestProgress.progress > 0) {
  status = "in_progress";
} else {
  status = "pending";
}

return {
  status,
  progressPercent,
  details: latestProgress,
};
```

#### Target Code:

```typescript
// No progress data yet for this stage
if (stageProgresses.length === 0) {
  return {
    status: "pending",
    iteration: null,
    maxIterations: null,
    progressPercent: 0,
    details: null,
  };
}

// Use the most recent progress event (array is ordered by created_at)
const latestProgress = stageProgresses[stageProgresses.length - 1];
if (!latestProgress) {
  return {
    status: "pending",
    iteration: null,
    maxIterations: null,
    progressPercent: 0,
    details: null,
  };
}
const progressPercent = Math.round(latestProgress.progress * 100);

// Determine status based on progress value
let status: "pending" | "in_progress" | "completed";
if (latestProgress.progress >= 1.0) {
  status = "completed";
} else if (latestProgress.progress > 0) {
  status = "in_progress";
} else {
  status = "pending";
}

return {
  status,
  iteration: latestProgress.iteration,
  maxIterations: latestProgress.max_iterations,
  progressPercent,
  details: latestProgress,
};
```

#### Why

Stages 1-4 are search-based with iteration data available from StageProgress. The iteration field is 1-based (from backend). max_iterations represents the search budget.

---

## Step 4: Update Stage Header Render Logic for Conditional Display

### File: `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx`

**Action**: Modify
**Lines**: 332-353

#### Current Code (lines 348-352):

```typescript
                  <h3 className="text-base font-semibold text-white">
                    Stage {stage.id}: {stage.title}
                    {info.status !== "pending" && (
                      <span className="ml-2 text-slate-400">({info.progressPercent}%)</span>
                    )}
                  </h3>
```

#### Target Code:

Add `latestPaperEvent` extraction after line 341 (bestNode definition):

```typescript
const latestPaperEvent =
  isPaperGeneration && paperGenerationProgress.length > 0
    ? paperGenerationProgress[paperGenerationProgress.length - 1]
    : null;
```

Then add `currentStepIndex` computation after latestPaperEvent:

```typescript
const currentStepIndex = latestPaperEvent?.step
  ? PAPER_GENERATION_STEPS.findIndex((s) => s.key === latestPaperEvent.step)
  : -1;
```

Then replace the h3 content (lines 348-352):

```typescript
                  <h3 className="text-base font-semibold text-white">
                    Stage {stage.id}: {stage.title}
                    {/* Stages 1-4: Show iteration count for in_progress */}
                    {info.status === "in_progress" && !isPaperGeneration && info.iteration !== null && (
                      <span className="ml-2 text-slate-400">
                        — Iteration {info.iteration} of {info.maxIterations}
                      </span>
                    )}
                    {/* Stages 1-4: Show completion iteration count for completed */}
                    {info.status === "completed" && !isPaperGeneration && info.iteration !== null && (
                      <span className="ml-2 text-slate-400">
                        — Completed in {info.iteration} iterations
                      </span>
                    )}
                    {/* Stage 5: Show step name + step count for in_progress */}
                    {isPaperGeneration && info.status === "in_progress" && latestPaperEvent?.step && (
                      <span className="ml-2 text-slate-400">
                        — {STEP_LABELS[latestPaperEvent.step]} (Step {currentStepIndex + 1} of {PAPER_GENERATION_STEPS.length})
                      </span>
                    )}
                    {/* Stage 5: Show completed message */}
                    {isPaperGeneration && info.status === "completed" && (
                      <span className="ml-2 text-slate-400">
                        — Completed in {PAPER_GENERATION_STEPS.length} steps
                      </span>
                    )}
                  </h3>
```

#### Why

- Stages 1-4 in_progress: Shows "Iteration X of Y" to indicate search attempts (not linear progress)
- Stages 1-4 completed: Shows "Completed in X iterations" to reveal actual effort required
- Stage 5 in_progress: Shows "Step Name (Step X of 4)" - unified format with Stages 1-4
- Stage 5 completed: Shows "Completed in 4 steps" - consistent with Stages 1-4
- Null checks prevent rendering for pending stages

---

## Verification

### Tests to Run

```bash
cd frontend
npm run lint
npm run type-check
```

### Manual Checks

- [ ] Stage 1-4 in progress shows "— Iteration X of Y" format
- [ ] Stage 1-4 completed shows "— Completed in X iterations" format
- [ ] Stage 5 in progress shows "— Step Name (Step X of 4)" format
- [ ] Stage 5 completed shows "— Completed in 4 steps" format
- [ ] Pending stages show no progress indicator (no text after title)
- [ ] No TypeScript errors in StageInfo interface satisfaction

## Rollback

If issues arise:

```bash
git checkout -- frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx
```

---

## Summary of Changes

| Step | Lines     | Change                                                          |
| ---- | --------- | --------------------------------------------------------------- |
| 1    | After 210 | Add STEP_LABELS constant (7 lines)                              |
| 2    | 253-281   | Add iteration: null, maxIterations: null to 3 Stage 5 returns   |
| 3    | 291-324   | Add iteration/maxIterations fields to 3 Stages 1-4 returns      |
| 4    | 332-353   | Update render logic with conditional display + latestPaperEvent |
