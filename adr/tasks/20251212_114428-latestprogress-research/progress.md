# 🔄 Progress: Stage-Based Progress Tracking

**Created**: 2025-12-12

## Goal

Change frontend progress display from iteration-based (within stages) to stage-based (20% per completed stage): Stage 1→20%, Stage 2→40%, Stage 3→60%, Stage 4→80%, Stage 5→100%.

## Status

**Phase**: ✅ COMPLETE
**Progress**: 3 of 3 steps complete

## ✅ Completed

- [x] Research: Understand `latestProgress` data flow
  - Created: `adr/tasks/20251212_114428-latestprogress-research/research.md`
- [x] Understand who sends events (backend research_pipeline emits `RunStageProgressEvent`)
- [x] Plan implementation approach (frontend-only change)
- [x] Updated `research-run-stats.tsx`
  - Added `extractStageSlug()` helper
  - Added `calculateOverallProgress()` function
  - Changed props to accept `stageProgress: StageProgress[]`
  - Updated to display stage-based progress (20% per completed stage)
- [x] Updated `page.tsx`
  - Changed to pass `stageProgress={stage_progress}` prop
- [x] Tested - all lint checks pass ✓

## 🎯 Key Decisions

| Decision | Choice                 | Rationale                                                                 |
| -------- | ---------------------- | ------------------------------------------------------------------------- |
| Display  | Overall only           | User chose to show only stage-based progress, not within-stage iterations |
| Approach | Frontend-only          | Backend already emits per-stage progress; no backend changes needed       |
| Logic    | Count completed stages | Each stage that reaches `progress >= 1.0` = 20%                           |

## 🚧 Current Blocker

None - ready to begin implementation

## 📁 Files

**Created**:

- `adr/tasks/20251212_114428-latestprogress-research/research.md`

**To Modify**:

- `frontend/src/features/research/components/run-detail/research-run-stats.tsx`
- `frontend/src/app/(dashboard)/research/[runId]/page.tsx`

## ▶️ Implementation Steps

**Step 1**: Add helpers to research-run-stats.tsx:

```typescript
const extractStageSlug = (stageName: string): string => {...}
const STAGE_ORDER = ["initial_implementation", "baseline_tuning", "creative_research", "ablation_studies", "paper_generation"]
function calculateOverallProgress(stageProgress: StageProgress[]): number {...}
```

**Step 2**: Update ResearchRunStatsProps interface to accept `stageProgress: StageProgress[]`

**Step 3**: Modify component to call `calculateOverallProgress()` instead of showing `latestProgress.progress * 100`

**Step 4**: Update page.tsx line 124 to pass `stageProgress={stage_progress}`
