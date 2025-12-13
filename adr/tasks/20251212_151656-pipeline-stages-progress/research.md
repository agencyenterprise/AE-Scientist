## 🔍 Feature Area: Pipeline Stages Progress System

## Summary

The Pipeline Stages progress system tracks 5 research pipeline stages (Baseline Implementation → Baseline Tuning → Creative Research → Ablation Studies → Paper Generation). Stages 1-4 use node-based progress tracking via `StageProgress` and `SubstageEvent` types, while Stage 5 uses step-based tracking via `PaperGenerationEvent`. Progress updates flow through SSE (Server-Sent Events) in real-time and are visualized using segmented progress bars.

## Code Paths Found

| File                                                                                | Lines   | Purpose                                                                                                                             | Action    |
| ----------------------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 22-53   | Defines 5 pipeline stages with metadata (id, key, title, description)                                                               | reference |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 64-81   | Extracts stage slug from backend format (e.g., "1_initial_implementation_1_preliminary" → "initial_implementation")                 | reference |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 244-320 | `getStageInfo()`: Determines stage status (pending/in_progress/completed) and progress percentage from latest progress event        | reference |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 133-177 | `getNodeSegments()`: Creates segments for node-based progress (Stages 1-4), falls back to synthetic segments from aggregate data    | reference |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 211-231 | `getPaperGenerationSegments()`: Creates segments for step-based progress (Stage 5), shows only completed and current steps          | reference |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 105-127 | `SegmentedProgressBar`: Unified progress bar component rendering segments with tooltips                                             | reference |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 184-197 | `getBestNodeForStage()`: Retrieves most recent best node selection for a stage                                                      | reference |
| `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx` | 327-383 | Main render: Maps through stages, displays status badges, progress bars, and best node info                                         | reference |
| `frontend/src/types/research.ts`                                                    | 78-90   | `StageProgressApi`: Backend type with iteration, progress, nodes (total/buggy/good), best_metric, ETA                               | reference |
| `frontend/src/types/research.ts`                                                    | 174-186 | `StageProgress`: Frontend type (same structure as API for SSE compatibility)                                                        | reference |
| `frontend/src/types/research.ts`                                                    | 107-112 | `SubstageEventApi`: Represents individual node events with stage, summary, created_at                                               | reference |
| `frontend/src/types/research.ts`                                                    | 195-200 | `SubstageEvent`: Frontend type for node events                                                                                      | reference |
| `frontend/src/types/research.ts`                                                    | 114-123 | `PaperGenerationEventApi`: Step-based progress for Stage 5 with step, substep, progress, step_progress                              | reference |
| `frontend/src/types/research.ts`                                                    | 202-211 | `PaperGenerationEvent`: Frontend type for paper generation progress                                                                 | reference |
| `frontend/src/types/research.ts`                                                    | 135-141 | `BestNodeSelectionApi`: Tracks best node selection per stage with node_id and reasoning                                             | reference |
| `frontend/src/types/research.ts`                                                    | 230-236 | `BestNodeSelection`: Frontend type for best node selections                                                                         | reference |
| `frontend/src/features/research/hooks/useResearchRunSSE.ts`                         | 122-156 | SSE event handling: Routes events to callbacks based on type (stage_progress, paper_generation_progress, best_node_selection, etc.) | reference |
| `frontend/src/features/research/hooks/useResearchRunDetails.ts`                     | 54-63   | `handleStageProgress()`: Appends new progress events to state array                                                                 | reference |
| `frontend/src/features/research/hooks/useResearchRunDetails.ts`                     | 87-96   | `handlePaperGenerationProgress()`: Appends paper generation events to state array                                                   | reference |
| `frontend/src/features/research/hooks/useResearchRunDetails.ts`                     | 98-107  | `handleBestNodeSelection()`: Appends best node selections to state array                                                            | reference |
| `frontend/src/features/research/components/run-detail/research-stage-progress.tsx`  | 12-52   | Legacy individual stage progress component (shows iteration, best_metric, nodes, simple progress bar)                               | reference |

**Action legend**: `modify` (needs changes), `reference` (read only)

## Key Patterns

### Data Flow Architecture

1. **Backend → SSE Stream**: Server sends typed events (`stage_progress`, `paper_generation_progress`, `best_node_selection`)
2. **SSE Hook → State Updates**: `useResearchRunSSE` parses events and triggers callbacks
3. **Details Hook → Component State**: `useResearchRunDetails` maintains arrays of events, appending new ones
4. **Component → Rendering**: `ResearchPipelineStages` processes accumulated events to derive current state

### Dual Progress Models

- **Stages 1-4 (Node-based)**: Progress measured by nodes explored (good_nodes, buggy_nodes, total_nodes)
  - Primary data: `StageProgress[]` with aggregate metrics
  - Detail data: `SubstageEvent[]` with individual node summaries
  - Fallback: If no node events, synthesize segments from aggregate `total_nodes`
- **Stage 5 (Step-based)**: Progress measured by completion of 4 sequential steps
  - Steps: plot_aggregation → citation_gathering → paper_writeup → paper_review
  - Data: `PaperGenerationEvent[]` with progress (0.0-1.0) and current step
  - Rendering: Only shows completed + current step (not future steps)

### Stage Status Derivation

- **pending**: No progress data yet (progress === 0 or no events)
- **in_progress**: 0 < progress < 1.0
- **completed**: progress >= 1.0

### Stage Naming Convention

Backend format: `{stage_number}_{stage_slug}_{substage_number}_{substage_name}`

- Example: `"1_initial_implementation_1_preliminary"`
- Extracted slug: `"initial_implementation"` (used for matching with PIPELINE_STAGES)

## Integration Points

- `useResearchRunSSE` (SSE hook) → event callbacks → `useResearchRunDetails` (state manager)
- `useResearchRunDetails` → `details.stage_progress[]` → `ResearchPipelineStages` (visualization)
- `ResearchPipelineStages` → `extractStageSlug()` → matches backend stages to UI stage definitions
- `ResearchPipelineStages.getStageInfo()` → uses latest event from sorted array to determine current status
- `SegmentedProgressBar` → renders segments with Tooltip for both node-based and step-based progress

## Constraints Discovered

### Type System

- Frontend types intentionally use snake_case (not camelCase) to match SSE event structure from backend
- Comment at `frontend/src/types/research.ts:154`: "Frontend types (camelCase) - using same structure for SSE compatibility"
- This enables direct assignment of SSE events without transformation

### Progress Bar Segments

- Node segments: Each explored node gets one segment (sorted chronologically)
- Fallback: When no `SubstageEvent[]` exists, derive segments from `total_nodes` in latest `StageProgress`
- Paper generation segments: Only shows completed + current steps (not all 4 steps upfront)

### Best Node Display

- Only shown for Stages 1-4 (not for paper generation)
- Uses most recent `BestNodeSelection` event for each stage
- Node ID truncated: keeps first 6 + last 4 chars with ellipsis (e.g., `abc123…xyz9`)
- Reasoning text shown with scrollbar if exceeds 24px height

### Stage Progress Array Handling

- Arrays are append-only (new events pushed to end)
- Latest state derived from last element: `stageProgresses[stageProgresses.length - 1]`
- Multiple substages within a stage handled by filtering on extracted slug, then using latest

### Empty States

- Stages 1-4 empty: "No nodes yet"
- Stage 5 empty: "No steps yet"
- Both use same `SegmentedProgressBar` component with different `emptyMessage` prop
