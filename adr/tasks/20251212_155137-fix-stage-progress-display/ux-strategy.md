# UX Strategy: Fix Misleading Progress Percentage Display in Pipeline Stages

## User Context

**Job to be done:** "When I'm monitoring a research run, I want to understand what the system is actually doing, so I can accurately gauge activity and completion likelihood"

**User type:** Expert/Regular, Daily/Weekly usage

**Complexity:** AI-system - needs transparency, showing that stages are search-based (not linear progress)

**Riskiest assumption:** Users currently assume "60%" means "60% done" when it really means "6 of 10 attempts, could finish on next attempt or take all remaining tries"

**Test plan:** Ship change, monitor if support questions decrease about "why did it finish at 30%?" or "stuck at 90%"

**Craft moment:** The iteration display in stage headers (primary visibility point)

---

## Principles Applied

**Primary:** Principle #5 - Translate Complexity
**Why:** The underlying search-based iteration model is complex. Users see "60%" and mentally translate to linear progress ("60% of work done"), but the reality is non-linear search ("tried 6 times, might succeed next or need all 10"). We need to translate this complexity into honest language.

**Secondary:** Principle #2 - Increase Agency
**Why:** AI/agent system transparency. By showing "Iteration 6 of 10" instead of "60%", users understand they're observing search attempts, not deterministic progress. This increases their agency to interpret what's happening.

**Also relevant:** Principle #3 - Spend Craft on the Right Things
**Why:** The stage header is high-visibility and shapes user perception of the entire pipeline. Getting this right prevents misunderstanding across all stages.

---

## Recommended Approach: Iteration-Based Display with Search Semantics

### Layout

```
┌───────────────────────────────────────────────────────────────┐
│ Stage 1: Baseline Implementation — Iteration 6 of 10          │ (HIGH CRAFT)
│                                        [IN PROGRESS] ←──────────┐
├───────────────────────────────────────────────────────────────┤
│ ████████████ (segmented node progress bar)                    │
├───────────────────────────────────────────────────────────────┤
│ Current Best Node: a3b4c5...                                  │
│ [reasoning scrollable area]                                   │
└───────────────────────────────────────────────────────────────┘

For completed stages:
┌───────────────────────────────────────────────────────────────┐
│ Stage 1: Baseline Implementation — Completed in 8 iterations  │
│                                        [COMPLETED]             │
├───────────────────────────────────────────────────────────────┤
│ ████████████████ (all nodes shown)                            │
└───────────────────────────────────────────────────────────────┘

For Stage 5 (Paper Generation):
┌───────────────────────────────────────────────────────────────┐
│ Stage 5: Paper Generation — Citation Gathering (45%)          │
│                                        [IN PROGRESS]           │
├───────────────────────────────────────────────────────────────┤
│ ████ (step-based progress bar)                                │
└───────────────────────────────────────────────────────────────┘
```

### Information Hierarchy

1. **Stage title** - Always visible, identifies the stage
2. **Iteration/completion indicator** - NEW: Shows "Iteration X of Y" or "Completed in X iterations"
   - Active stages: "Iteration 6 of 10" (replaces "60%")
   - Completed stages: "Completed in 8 iterations" (shows final iteration count)
   - Stage 5: Keep percentage since it's step-based, not search-based
3. **Status badge** - IN PROGRESS / COMPLETED (existing, keep unchanged)
4. **Segmented progress bar** - Shows individual nodes/steps (existing, keep unchanged)
5. **Best node display** - Shows current best solution (existing, keep unchanged)

### Key Interactions

**Primary action:** Monitor stage progress by reading stage header

- Display: "Iteration X of Y" for active search stages (1-4)
- Feedback: Number increases as search continues, no false precision
- User understanding: "The system has tried X times and might succeed on the next attempt"

**For completed stages:**

- Display: "Completed in X iterations"
- Feedback: Shows historical context of how many tries it took
- User understanding: "This stage found a good solution after X attempts"

**For Stage 5 (Paper Generation):**

- Display: "Citation Gathering (45%)" - keep current step name + percentage
- Rationale: Step-based progress IS linear and deterministic (not search-based)
- User understanding: "This is 45% through the current step"

**For AI/Agent Transparency:**

- Iteration count reveals search nature: Users see the system is exploring, not just linearly executing
- Completed iteration count: Shows actual effort required, validates non-linear nature
- No false precision: "Iteration 6 of 10" doesn't promise completion timeline

---

## Craft vs Ship Fast

### High Craft (Principle #3)

- **Stage header iteration display**: Clear, semantic labeling that accurately represents the search model
  - Active: "Iteration X of Y" (no percentage)
  - Completed: "Completed in X iterations"
  - Must be immediately readable and honest about what's happening

### Ship Fast

- Status badge (keep existing: IN PROGRESS / COMPLETED)
- Segmented progress bar (keep existing visual)
- Best node display (keep existing)
- No animation changes needed
- No tooltip additions required for V1

---

## V1 Scope (Principle #1)

**Hypothesis:**
"We believe expert and regular users need honest iteration counts because percentage implies false precision in search-based stages. We'll know we're right when users stop asking 'why did it finish at 30%?' or 'stuck at 90%?'"

**Minimum to test:**

**Stages 1-4 (search-based):**

- Active stages: Replace `(60%)` with `— Iteration 6 of 10`
- Completed stages: Replace `(100%)` with `— Completed in 8 iterations`

**Stage 5 (step-based):**

- Keep current format: `— Citation Gathering (45%)`
- Rationale: Step-based progress is actually linear

**Skip for V1:**

- Tooltip explanations of search vs linear progress
- Animation changes
- Separate component refactoring
- Historical iteration trend charts
- Estimated time remaining (ETA already exists in data, but don't add to UI yet)

---

## Design Checklist

**Principle #5 - Translate Complexity:**

- [ ] Stage headers show "Iteration X of Y" for search stages (not percentage)
- [ ] Completed stages show "Completed in X iterations" (provides outcome context)
- [ ] Stage 5 keeps percentage since it's step-based (different mental model)

**Principle #2 - Increase Agency:**

- [ ] Users can see iteration attempts, understanding it's a search process
- [ ] No false precision - iteration count reveals non-deterministic nature
- [ ] Completed stages reveal actual effort (transparency into system behavior)

**Principle #3 - Spend Craft:**

- [ ] Stage header format is the high-craft element (primary visibility)
- [ ] Text is clear and semantic: "Iteration" not "Try" or "Attempt"
- [ ] Existing visual elements (badges, bars) ship fast unchanged

**Principle #1 - Ship to Learn:**

- [ ] V1 only changes text display format (minimal scope)
- [ ] Can validate hypothesis quickly (<1 day implementation)
- [ ] Easy to iterate based on user feedback

**Principle #4 - Steelman User Needs:**

- [ ] Respects that users need honest information about system state
- [ ] Doesn't assume users want false comfort of linear percentages
- [ ] Treats users as capable of understanding search-based iteration

---

## Implementation Specifics

### File: `research-pipeline-stages.tsx`

**Lines 348-353** - Stage header display logic:

Current code:

```tsx
<h3 className="text-base font-semibold text-white">
  Stage {stage.id}: {stage.title}
  {info.status !== "pending" && (
    <span className="ml-2 text-slate-400">({info.progressPercent}%)</span>
  )}
</h3>
```

Proposed change:

```tsx
<h3 className="text-base font-semibold text-white">
  Stage {stage.id}: {stage.title}
  {info.status === "in_progress" &&
    !isPaperGeneration &&
    info.iteration !== null && (
      <span className="ml-2 text-slate-400">
        — Iteration {info.iteration} of {info.maxIterations}
      </span>
    )}
  {info.status === "completed" &&
    !isPaperGeneration &&
    info.iteration !== null && (
      <span className="ml-2 text-slate-400">
        — Completed in {info.iteration} iterations
      </span>
    )}
  {isPaperGeneration && info.status !== "pending" && (
    <span className="ml-2 text-slate-400">
      {latestPaperEvent?.step && `— ${STEP_LABELS[latestPaperEvent.step]} `}(
      {info.progressPercent}%)
    </span>
  )}
</h3>
```

**Lines 82-93** - StageInfo interface already has the data:

- `iteration: number | null` (current iteration, 1-based)
- `maxIterations: number | null` (budget)
- `progressPercent: number | null` (for Stage 5 only)

**Lines 249-325** - `getStageInfo()` already extracts iteration data from `StageProgress`:

- Line 308: `progressPercent` is calculated but will only be used for Stage 5
- Line 323: `details: latestProgress` contains iteration/max_iterations

**Required changes:**

1. Update StageInfo interface to surface iteration/maxIterations at top level
2. Modify getStageInfo to populate these fields from latestProgress.iteration/max_iterations
3. Update stage header rendering logic (lines 348-353) per above
4. Add STEP_LABELS mapping at top of file for Stage 5 step names

---

**APPROVAL REQUIRED**

Reply with:

- **"proceed"** - Strategy approved, continue to next phase
- **"modify: [feedback]"** - Adjust recommendations
- **"skip"** - Skip UX strategy for this feature

Waiting for approval...
