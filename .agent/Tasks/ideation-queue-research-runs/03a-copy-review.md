# Copy Review: Ideation Queue Research Runs Display

## Agent
copy-reviewer

## Timestamp
2025-12-08 14:30

## Files Reviewed
| File | Copy Elements Found |
|------|---------------------|
| `IdeationQueueCard.tsx` | Button labels ("Runs"), timestamps ("Created", "Updated"), expand/collapse icons |
| `IdeationQueueRunItem.tsx` | Status badges, truncated run IDs, GPU type labels, timestamps |
| `IdeationQueueRunsList.tsx` | Empty state ("No research runs yet"), error messages, retry button, "+N more runs" indicator |
| `useConversationResearchRuns.ts` | Error message ("Failed to fetch research runs") |

## Brand Voice Check
- Guidelines found: No (no brand-voice.md or copy-guidelines.md exists)
- Reference: Used existing `.agent/Tasks/research-history-home/03a-copy-review.md` for consistency patterns
- Compliance: Mostly consistent with existing app patterns

---

## Summary

The copy in the research runs display feature is generally functional and consistent with existing patterns in the codebase. The main issues are:

1. **Accessibility gaps** - The expand/collapse button and run item buttons lack aria-labels for screen readers
2. **Minor terminology inconsistency** - "Runs" button label is terse; could be more descriptive
3. **Error message clarity** - Technical fallback error message could be more user-friendly

Overall the copy follows existing patterns well, particularly matching the `IdeationQueueEmpty` and `ResearchHistoryEmpty` components' style.

---

## Findings

### Must Fix (Clarity/Accessibility Issues)

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| `IdeationQueueCard.tsx:70-85` | Expand button has no `aria-label` | Screen readers only hear "Runs" without understanding it's an expand/collapse toggle | Add `aria-label={isExpanded ? "Hide research runs" : "Show research runs"}` |
| `IdeationQueueRunItem.tsx:32-53` | Button has no `aria-label` | Screen readers don't understand the purpose of this clickable element; only reads out status, ID fragments, and GPU type | Add `aria-label={\`View research run ${runId}, status: ${status}\`}` |
| `useConversationResearchRuns.ts:52` | "Failed to fetch research runs" | Technical language when underlying error is unknown; doesn't tell user what to do | "Couldn't load research runs. Please try again." |

### Should Fix (Consistency/Tone Issues)

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| `IdeationQueueCard.tsx:79` | "Runs" | Very terse - users may not immediately understand this means "research runs"; inconsistent with more descriptive labels elsewhere | "Research runs" or "Show runs" (with collapse state: "Hide runs") |
| `IdeationQueueRunsList.tsx:119-120` | "+{n} more runs" | Uses `+` symbol which may not be screen-reader friendly; slightly casual | "{n} more runs" or "and {n} more" |

### Suggestions (Polish)

| Location | Current Copy | Suggestion |
|----------|--------------|------------|
| `IdeationQueueRunsList.tsx:40` | "No research runs yet" | This is good and matches the pattern from `IdeationQueueEmpty` ("No ideas yet"). Consider adding a subtle call-to-action: "No research runs yet. Start one from the idea details." - but current copy is acceptable for MVP |
| `IdeationQueueRunItem.tsx:49` | GPU type displayed raw (e.g., "RTX A4000") | GPU types are currently displayed as-is from the API. Consider humanizing if needed (e.g., "GPU: RTX A4000") - but current format is acceptable for technical users |
| `IdeationQueueCard.tsx:65-67` | "Created {time}" / "Updated {time}" | Consistent with existing card style. Consider whether both are needed or if just "Updated {time}" suffices - but both are fine |

---

## Terminology Consistency Check

| Term | Usage in New Code | Usage Elsewhere in App | Status |
|------|-------------------|------------------------|--------|
| "research runs" | IdeationQueueRunsList empty state | ResearchHistoryList, research-utils.tsx | CONSISTENT |
| "Runs" | IdeationQueueCard expand button | N/A (new pattern) | NEW - needs context |
| Status labels (Completed, Running, Failed, Pending) | Via getStatusBadge() | ResearchHistoryCard, research-utils.tsx | CONSISTENT (reused) |
| "No ... yet" pattern | "No research runs yet" | "No ideas yet", "No conversations yet", "No research history yet" | CONSISTENT |
| "Retry" | RunsListError button | Used elsewhere in app | CONSISTENT |
| Error messages | "Failed to fetch research runs" | Various patterns used | NEEDS REVIEW |

---

## Accessibility Audit

| Check | Status | Notes |
|-------|--------|-------|
| Button labels | NEEDS WORK | Both expand button and run item button lack aria-labels |
| Error messages | PASS | Error message displayed with retry option |
| Empty state | PASS | Clear, simple message matching app patterns |
| Loading state | PASS | Skeleton provides visual feedback (no text needed) |
| Status badges | PASS | Reuses existing accessible `getStatusBadge()` with icons + text |
| Link/navigation text | NEEDS WORK | Run items are clickable but destination not announced |
| Icon-only elements | PASS | ChevronDown/Up icons are paired with "Runs" text |
| Color contrast | PASS | Uses established design system colors |
| Focus indicators | PASS | Buttons have hover/focus states from Tailwind |

### WCAG Compliance Notes

1. **WCAG 2.4.4 Link Purpose**: The run item buttons navigate to `/research/{runId}` but this isn't communicated to assistive technology users
2. **WCAG 4.1.2 Name, Role, Value**: The expand/collapse button state (expanded/collapsed) isn't announced

---

## Copy Comparison: New vs Existing Patterns

| Element | IdeationQueueEmpty (existing) | IdeationQueueRunsList (new) | Alignment |
|---------|-------------------------------|----------------------------|-----------|
| Empty heading | "No ideas yet" | "No research runs yet" | ALIGNED |
| Empty subtext | "Import conversations..." | (none) | OK - runs are nested, less context needed |
| Error retry | N/A | "Retry" | ALIGNED with app patterns |

| Element | ResearchHistoryList (existing) | IdeationQueueRunsList (new) | Alignment |
|---------|--------------------------------|----------------------------|-----------|
| Empty state | "No research history yet" | "No research runs yet" | ALIGNED |
| Error message | "Try again" button | "Retry" button | MINOR DIFF - both acceptable |
| Loading | Skeleton | Skeleton | ALIGNED |

---

## Summary Counts

| Category | Count |
|----------|-------|
| Must Fix | 3 |
| Should Fix | 2 |
| Suggestions | 3 |

---

## Recommended Fixes for Executor

### Priority 1 (Must Fix - Accessibility)

1. **IdeationQueueCard.tsx:70-85** - Add aria-label to expand/collapse button:
```tsx
<button
  onClick={handleExpandToggle}
  type="button"
  aria-label={isExpanded ? "Hide research runs" : "Show research runs"}
  aria-expanded={isExpanded}
  className={...}
>
```

2. **IdeationQueueRunItem.tsx:32-53** - Add aria-label to run item button:
```tsx
<button
  onClick={handleClick}
  type="button"
  aria-label={`View research run ${truncateRunId(runId)}, status: ${status}`}
  className={...}
>
```

3. **useConversationResearchRuns.ts:48-53** - Improve error message:
```tsx
error:
  error instanceof Error
    ? error.message
    : error
      ? "Couldn't load research runs. Please try again."
      : null,
```

### Priority 2 (Should Fix - Clarity)

4. **IdeationQueueCard.tsx:79** - Make button label more descriptive:
```tsx
{isExpanded ? "Hide runs" : "Show runs"}
// OR simply:
Research runs
```

5. **IdeationQueueRunsList.tsx:119-120** - Remove `+` symbol:
```tsx
<span className="text-xs text-slate-500">
  {runs.length - 5} more runs
</span>
```

### Priority 3 (Nice to Have)

6. Consider adding brief context to empty state (optional for MVP)
7. Consider aria-live region for error/loading states (optional enhancement)

---

## Specific Code Changes

### File: IdeationQueueCard.tsx (lines 70-85)

**Current:**
```tsx
<button
  onClick={handleExpandToggle}
  type="button"
  className={cn(...)}
>
  Runs
  {isExpanded ? (
    <ChevronUp className="h-3 w-3" />
  ) : (
    <ChevronDown className="h-3 w-3" />
  )}
</button>
```

**Suggested:**
```tsx
<button
  onClick={handleExpandToggle}
  type="button"
  aria-label={isExpanded ? "Hide research runs" : "Show research runs"}
  aria-expanded={isExpanded}
  className={cn(...)}
>
  {isExpanded ? "Hide runs" : "Show runs"}
  {isExpanded ? (
    <ChevronUp className="h-3 w-3" aria-hidden="true" />
  ) : (
    <ChevronDown className="h-3 w-3" aria-hidden="true" />
  )}
</button>
```

### File: IdeationQueueRunItem.tsx (lines 31-53)

**Current:**
```tsx
<button
  onClick={handleClick}
  type="button"
  className={cn(...)}
>
```

**Suggested:**
```tsx
<button
  onClick={handleClick}
  type="button"
  aria-label={`View research run ${truncateRunId(runId)}, status: ${status}`}
  className={cn(...)}
>
```

### File: useConversationResearchRuns.ts (line 52)

**Current:**
```tsx
? "Failed to fetch research runs"
```

**Suggested:**
```tsx
? "Couldn't load research runs. Please try again."
```

### File: IdeationQueueRunsList.tsx (line 120)

**Current:**
```tsx
+{runs.length - 5} more runs
```

**Suggested:**
```tsx
{runs.length - 5} more runs
```

---

## APPROVAL REQUIRED

Please review the copy suggestions above. Reply with:

- **"proceed"** or **"yes"** - Apply all recommended fixes (Priority 1 + 2)
- **"proceed all"** - Apply all fixes including Priority 3
- **"apply: [numbers]"** - Apply only specific fixes (e.g., "apply: 1, 2, 3")
- **"modify: [feedback]"** - Adjust recommendations based on your feedback
- **"elaborate"** - Provide more details about specific suggestions
- **"skip"** - Skip copy fixes for now

**Key decision needed:** For the expand button label (fix #4), choose between:
- A) Dynamic text: "Show runs" / "Hide runs"
- B) Static text: "Research runs" (current pattern with just "Runs")
- C) Keep as-is: "Runs"

Waiting for your approval...
