# Research: latestProgress Data Flow

## Summary

`latestProgress` is the most recent stage progress update for a research run. It's extracted from the `stage_progress` array and passed to `ResearchRunStats` to display current stage, progress percentage, and other run metrics. The data originates from SSE (Server-Sent Events) and is accumulated in the `useResearchRunDetails` hook.

## Code Paths Found

| File                                                                          | Lines            | Purpose                            | Action    |
| ----------------------------------------------------------------------------- | ---------------- | ---------------------------------- | --------- |
| `frontend/src/app/(dashboard)/research/[runId]/page.tsx`                      | 97               | Extract latest progress from array | reference |
| `frontend/src/app/(dashboard)/research/[runId]/page.tsx`                      | 124              | Pass to ResearchRunStats component | reference |
| `frontend/src/features/research/components/run-detail/research-run-stats.tsx` | 8, 17, 21, 29-30 | Consume and display progress data  | reference |
| `frontend/src/features/research/hooks/useResearchRunDetails.ts`               | 53-62            | Handle SSE stage_progress events   | reference |
| `frontend/src/types/research.ts`                                              | 165-177          | StageProgress type definition      | reference |

**Action legend**: `reference` (read only) - no modifications needed

## Data Flow

### 1. Data Origin (SSE Events)

```
SSE Stream → useResearchRunSSE (hooks/useResearchRunSSE.ts:124)
           → handleStageProgress callback (hooks/useResearchRunDetails.ts:53-62)
           → Appends to stage_progress array in state
```

### 2. Data Extraction (Page Component)

```
page.tsx:95-97
├─ Destructures stage_progress from details
└─ Extracts last element: latestProgress = stage_progress[stage_progress.length - 1]
```

### 3. Data Consumption (Stats Component)

```
ResearchRunStats (research-run-stats.tsx:16-22)
├─ Receives latestProgress as prop (line 8, 17)
├─ Calculates progress percent (line 21)
└─ Displays:
    ├─ Current stage name (line 29-30)
    └─ Progress percentage (line 36)
```

## StageProgress Type Structure

From `frontend/src/types/research.ts:165-177`:

```typescript
export interface StageProgress {
  stage: string; // Current stage name
  iteration: number; // Current iteration
  max_iterations: number; // Total iterations
  progress: number; // 0.0 - 1.0 decimal
  total_nodes: number; // Total nodes
  buggy_nodes: number; // Buggy nodes count
  good_nodes: number; // Good nodes count
  best_metric: string | null; // Best metric value
  eta_s: number | null; // ETA in seconds
  latest_iteration_time_s: number | null; // Last iteration time
  created_at: string; // Timestamp
}
```

## Integration Points

1. **SSE Event Handler** (`useResearchRunSSE.ts:124`)
   - Receives `stage_progress` events from backend
   - Triggers `onStageProgress` callback

2. **State Management** (`useResearchRunDetails.ts:53-62`)
   - Accumulates progress events in array
   - Each new event appends to `stage_progress`

3. **Display Component** (`research-run-stats.tsx:16-52`)
   - Shows current stage name
   - Calculates and displays progress percentage
   - Handles undefined state gracefully (shows "-")

## Key Patterns

- **Last Element Pattern**: `latestProgress = array[array.length - 1]` used to get most recent update
- **Optional Chaining**: Safe access with `latestProgress?.stage` to handle undefined
- **Progress Normalization**: `Math.round(progress * 100)%` converts 0.0-1.0 to percentage
- **Real-time Updates**: SSE pattern for live progress tracking

## Usage in Other Components

`latestProgress` is also used in:

- `research-pipeline-stages.tsx:160-162`: Extracts `good_nodes` and `buggy_nodes`
- `research-pipeline-stages.tsx:265-288`: Calculates progress percentages and status

## Constraints Discovered

1. **Array Access Safety**: Must handle empty `stage_progress` array (undefined `latestProgress`)
2. **Type Safety**: `StageProgress | undefined` type reflects potential empty state
3. **Progress Range**: Progress values are decimals 0.0-1.0, not percentages
4. **SSE Dependency**: Real-time updates require active SSE connection
