# Copy Review: Research History Feature

## Agent
copy-reviewer

## Timestamp
2025-12-03 18:45

## Files Reviewed
| File | Copy Elements Found |
|------|---------------------|
| `/frontend/src/features/research/components/ResearchHistoryList.tsx` | Header, entry count, error message, retry button |
| `/frontend/src/features/research/components/ResearchHistoryCard.tsx` | Title fallback, status badges, labels, timestamps, action buttons |
| `/frontend/src/features/research/components/ResearchHistoryEmpty.tsx` | Empty state heading and description |
| `/frontend/src/features/research/components/ResearchHistorySkeleton.tsx` | (No user-facing text - visual only) |

## Brand Voice Check
- Guidelines found: No (no brand-voice.md or copy-guidelines.md exists)
- Compliance: N/A - establishing patterns from existing codebase

---

## Summary

The Research History feature copy is generally clear and functional. The main terminology issue is a **conflicting message in the empty state** that references "hypothesis" when the user specifically requested changing from "hypothesis" to "research" terminology. There are also some minor consistency and accessibility improvements recommended.

---

## Findings

### Must Fix (Clarity/Accessibility Issues)

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| `ResearchHistoryEmpty.tsx:14` | "Submit your first hypothesis above to get started" | Uses "hypothesis" when user requested "research" terminology. Also, the form above uses "Create hypothesis" button, creating terminology confusion | "Start your first research above to get started" or align with form: "Create your first hypothesis above to get started" |
| `ResearchHistoryCard.tsx:82` | Button has no `aria-label` | Icon-only buttons and action links benefit from explicit aria-labels for screen readers | Add `aria-label={isCompleted ? "Relaunch experiment for [title]" : "View experiment [title]"}` |

### Should Fix (Consistency/Tone Issues)

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| `ResearchHistoryCard.tsx:42` | "waiting on ideation" | Lowercase inconsistent with orchestrator's "Waiting on ideation" in button label; also slightly informal | "Waiting for ideation" (title case, consistent preposition) |
| `ResearchHistoryCard.tsx:56` | "Ideation highlight" | Title case inconsistent - could be "IDEATION HIGHLIGHT" like other labels, but current style is fine | Keep as-is, but ensure consistency if other labels change |
| `ResearchHistoryList.tsx:55` | "Try again" | Generic error recovery text | "Retry" (more concise) or keep as-is (friendly tone) |
| `ResearchHistoryCard.tsx:71` | "launched {date}" | Lowercase "launched" alongside uppercase timestamp text looks slightly inconsistent | "Launched {date}" (sentence case) |

### Suggestions (Polish)

| Location | Current Copy | Suggestion |
|----------|--------------|------------|
| `ResearchHistoryEmpty.tsx:12` | "No research history yet" | Consider adding more context: "No research history yet" is clear, but could add encouragement |
| `ResearchHistoryCard.tsx:33` | "Untitled Research" | Consider "Untitled research" (sentence case) for consistency, or keep Title Case as it's a fallback name |
| `ResearchHistoryCard.tsx:37-38` | "running {stage}" | Stage name might be technical (e.g., "stage1"). Consider humanizing: "running Stage 1" or "running baseline" |
| `ResearchHistoryList.tsx:36` | "Last {n} entries" | Clear and functional. Could consider "Recent {n} runs" to match "research runs" terminology |

---

## Terminology Consistency Check

| Term | Usage in New Code | Usage Elsewhere in App | Recommendation |
|------|-------------------|------------------------|----------------|
| Research History | Header: "Research History" | Orchestrator uses "Hypothesis history" | CORRECT - matches user's request to change from "hypothesis" to "research" |
| hypothesis | Empty state: "Submit your first hypothesis" | Home page form: "Create hypothesis" button | INCONSISTENT - empty state should either match form ("hypothesis") or use "research" consistently |
| experiment | Buttons: "View experiment", "Relaunch experiment" | Orchestrator: "Launch experiment", "Relaunch experiment" | CONSISTENT |
| ideation | Badge: "waiting on ideation", Label: "Ideation highlight" | Orchestrator: "ideation running", "ideation queued", "Ideation highlight" | CONSISTENT |

### Key Terminology Decision Needed

The user requested changing "hypothesis" to "research" terminology. However:
- The main form on the home page still uses "Create hypothesis" button
- The app description says "AI Research Hypothesis Generator"
- The empty state says "Submit your first hypothesis"

**Options:**
1. **Full migration**: Change empty state to "Start your first research..." and eventually update the form too
2. **Keep hypothesis in forms, research in history**: The section is "Research History" but individual submissions are "hypotheses"
3. **Align with current form**: Keep "hypothesis" in empty state since form uses "Create hypothesis"

---

## Accessibility Audit

| Check | Status | Notes |
|-------|--------|-------|
| Button labels | NEEDS WORK | Action link in ResearchHistoryCard lacks aria-label |
| Error messages | PASS | Error message is displayed with icon; "Try again" button is clear |
| Form labels | N/A | No form inputs in these components |
| Link text | PASS | "Relaunch experiment" / "View experiment" are descriptive |
| Icon-only elements | PASS | Lightbulb and Clock icons are decorative (text provides context) |
| Empty state | PASS | Clear heading and actionable description |
| Loading state | PASS | Skeleton provides visual feedback (no text needed) |
| Color contrast | PASS | Using established design system colors (sky-200, slate-300, etc.) |

---

## Copy Comparison: Frontend vs Orchestrator

| Element | Orchestrator (HypothesisHistoryList.tsx) | Frontend (ResearchHistoryList.tsx) | Notes |
|---------|------------------------------------------|-----------------------------------|-------|
| Header | "Hypothesis history" | "Research History" | INTENTIONAL CHANGE per user request |
| Status: running | "ideation running" | "running {stage}" | Different context - orchestrator shows ideation status, frontend shows run status |
| Status: queued | "ideation queued" | "waiting on ideation" | Slightly different wording |
| Status: failed | "ideation failed" | "failed" | Frontend more generic |
| Button (disabled) | "Waiting on ideation" | N/A (status badge used) | Different UX pattern |
| Button (no experiments) | "Launch experiment" | N/A (only shows for existing runs) | N/A |
| Button (has experiments) | "Relaunch experiment" | "Relaunch experiment" | CONSISTENT |
| Hide functionality | Yes, with confirmation text | Not implemented | Scope difference |

---

## Summary Counts

| Category | Count |
|----------|-------|
| Must Fix | 2 |
| Should Fix | 4 |
| Suggestions | 4 |

---

## Recommended Fixes for Executor

### Priority 1 (Must Fix)
1. **ResearchHistoryEmpty.tsx:14**: Change "Submit your first hypothesis above to get started" to align with terminology decision (see options above)
2. **ResearchHistoryCard.tsx:78-83**: Add aria-label to the action Link

### Priority 2 (Should Fix)
3. **ResearchHistoryCard.tsx:42**: Change "waiting on ideation" to "Waiting for ideation" (or keep "waiting on ideation" but ensure consistency with orchestrator)
4. **ResearchHistoryCard.tsx:71**: Capitalize "launched" to "Launched"

### Priority 3 (Nice to Have)
5. Consider humanizing stage names in running status badge
6. Consider "Recent X runs" instead of "Last X entries"

---

## APPROVAL REQUIRED

Please review the copy suggestions. Reply with:
- **"proceed"** or **"yes"** - Apply all recommended fixes
- **"proceed with option 1/2/3"** - Apply fixes with specified terminology approach for "hypothesis" vs "research"
- **"apply: [specific fixes]"** - Apply only certain fixes (e.g., "apply: 1, 2, 4")
- **"elaborate"** - Provide more details about the suggestions
- **"skip"** - Skip copy fixes for now

**Terminology clarification needed**: Should the empty state say:
1. "Start your first research above to get started" (full migration to "research")
2. "Create your first hypothesis above to get started" (match form button)
3. "Submit a hypothesis above to start your research" (bridge both terms)

Waiting for your approval...
