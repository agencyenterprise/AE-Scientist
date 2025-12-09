# Copy Review: Conversation Status Badge

## Agent
copy-reviewer

## Timestamp
2025-12-09 16:15

## Files Reviewed
| File | Copy Elements Found |
|------|---------------------|
| `ConversationStatusBadge.tsx` | Badge labels: "Draft", "With Research" |
| `IdeationQueueCard.tsx` | Badge placement context, surrounding UI copy |

## Brand Voice Check
- Guidelines found: No (no brand-voice.md or copy-guidelines.md exists)
- Reference: Used existing copy review patterns from `.agent/Tasks/ideation-queue-research-runs/03a-copy-review.md` and `.agent/Tasks/conversation-status-tracking/03a-copy-review.md`
- Compliance: Following established codebase conventions

---

## Summary

The status badge copy is **minimal and functional**. The two labels ("Draft" and "With Research") are appropriately brief for the small badge size. However, there are some clarity and consistency considerations worth evaluating.

**Overall Assessment:** The copy is acceptable for the current implementation but could benefit from minor refinements for improved user understanding.

---

## Findings

### Must Fix (Clarity/Accessibility Issues)

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| None | - | - | No critical accessibility or clarity issues found |

The badge has no critical issues. It uses text labels (not icons alone), which is accessible. The badge is presentational and does not require aria-labels since the text content is self-describing.

### Should Fix (Consistency/Tone Issues)

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| ConversationStatusBadge.tsx:27 | "With Research" | Slightly inconsistent phrasing - "With Research" describes a state but doesn't match the pattern of other status labels (e.g., "Running", "Completed", "Pending" are single words or verb forms) | Consider: "Researched" or "Has Research" or "Active" |

### Suggestions (Polish)

| Location | Current Copy | Suggestion |
|----------|--------------|------------|
| ConversationStatusBadge.tsx:22 | "Draft" | Clear and appropriate. Could optionally be "New" if the goal is to encourage action, but "Draft" accurately describes the state. **Keep as-is.** |
| ConversationStatusBadge.tsx:27 | "With Research" | See analysis below for alternatives |

---

## Detailed Analysis: Badge Text

### "Draft" Label

**Current:** "Draft"

| Criteria | Assessment | Notes |
|----------|------------|-------|
| Clarity | PASS | Users understand "Draft" means incomplete/initial state |
| Brevity | PASS | Single word, fits small badge |
| Consistency | PASS | Matches common UX patterns (email drafts, document drafts) |
| Tone | PASS | Neutral, non-alarming |
| Actionability | NEUTRAL | Doesn't explicitly prompt action, but that's acceptable for a status indicator |

**Verdict:** Keep "Draft" as-is. It's clear, concise, and widely understood.

### "With Research" Label

**Current:** "With Research"

| Criteria | Assessment | Notes |
|----------|------------|-------|
| Clarity | PARTIAL | Users understand it has research, but may wonder "with what?" or "doing what?" |
| Brevity | PASS | Two words, fits small badge |
| Consistency | PARTIAL | Other status badges in the app use single words or verb forms: "Running", "Completed", "Pending", "Failed" |
| Tone | PASS | Neutral, informative |
| Actionability | PASS | Implies research has been initiated |

**Potential Issues:**
1. **Prepositional phrase** - "With Research" uses a preposition ("with") while other statuses don't
2. **Ambiguity** - Does "With Research" mean research is complete, in progress, or merely started?
3. **Length** - At 2 words, it's longer than the single-word "Draft"

**Alternative Options:**

| Option | Pros | Cons |
|--------|------|------|
| "With Research" (current) | Accurate; clearly indicates research exists | Prepositional; longer than other status labels |
| "Researched" | Single word; past tense matches "Completed" pattern | Could imply research is finished (misleading if running) |
| "Active" | Single word; implies ongoing activity | Too generic; doesn't mention research |
| "In Research" | Implies active process | Prepositional; could be confusing |
| "Has Research" | Clear; explicit | Prepositional; slightly awkward |
| "Research" | Shortest option | Could be confused as label category, not status |

**Recommendation:** The current "With Research" is acceptable but not ideal. Consider one of these alternatives in priority order:

1. **"Researched"** - Most concise, aligns with past-tense status pattern
2. **"Active"** - Simple, implies ongoing work (if research can be in multiple states)
3. **Keep "With Research"** - If the team prefers explicit clarity over brevity

---

## Terminology Consistency Check

| Term | Used In | Pattern | Consistency Status |
|------|---------|---------|-------------------|
| "Draft" | ConversationStatusBadge.tsx | Status label | CONSISTENT - matches common UX patterns |
| "With Research" | ConversationStatusBadge.tsx | Status label | PARTIAL - differs from single-word patterns elsewhere |
| "Completed" | research-utils.tsx:81 | Status label | Reference pattern (single word, past tense) |
| "Running" | research-utils.tsx:89 | Status label | Reference pattern (single word, present participle) |
| "Pending" | research-utils.tsx:108 | Status label | Reference pattern (single word, adjective) |
| "Failed" | research-utils.tsx:98 | Status label | Reference pattern (single word, past tense) |
| "IN PROGRESS" | research-pipeline-stages.tsx:275 | Status label | Reference pattern (ALL CAPS in that context) |

**Observation:** Research run status badges consistently use single-word labels. The conversation status badge breaks this pattern with "With Research" (two words with preposition).

---

## Comparison: Status Badge Patterns

### Research Run Statuses (from research-utils.tsx)
```
Completed  -> Completed    (single word, past tense)
Running    -> Running      (single word, present participle)
Failed     -> Failed       (single word, past tense)
Pending    -> Pending      (single word, adjective)
```

### Conversation Statuses (current)
```
draft          -> Draft          (single word - GOOD)
with_research  -> With Research  (two words - INCONSISTENT)
```

### Suggested Alignment
```
draft          -> Draft          (keep)
with_research  -> Researched     (align with past-tense pattern)
```

---

## Accessibility Audit

| Check | Status | Notes |
|-------|--------|-------|
| Color contrast | PASS | Draft: 4.6:1 (AA), With Research: 7.2:1 (AAA) per design guidance |
| Text labels | PASS | Both states use text (no icon-only badges) |
| Screen reader accessible | PASS | Text labels are self-describing |
| Non-interactive | PASS | Badge has no click handler, so no aria requirements |
| ARIA attributes | N/A | Not needed for presentational text badge |

---

## User Understanding Assessment

### Scenario Testing

**Scenario 1: New User**
> User sees card with "Draft" badge
> Understanding: "This is a new or incomplete item"
> Rating: Clear

**Scenario 2: New User**
> User sees card with "With Research" badge
> Understanding: "This item has research... but what does that mean? Is it done? In progress?"
> Rating: Somewhat clear, but could be confusing

**Scenario 3: Returning User**
> User familiar with the research workflow understands "With Research" means research runs have been started
> Rating: Clear (with context)

### Recommendation for Copy Clarity

If the primary audience is technical users familiar with the research pipeline, "With Research" is acceptable. If onboarding new users is a priority, consider:
- Adding tooltip on hover: "This conversation has research runs"
- Using more explicit label: "Has Research Runs" (longer but clearer)

---

## Summary Counts

| Category | Count |
|----------|-------|
| Must Fix | 0 |
| Should Fix | 1 |
| Suggestions | 2 |

---

## For Executor

### No Mandatory Changes Required

The current copy is functional and accessible. The following are optional improvements:

### Optional Improvement: Align "With Research" with Single-Word Pattern

**File:** `/Users/jarbasmoraes/code/ae/ae-scientist/AE-Scientist/frontend/src/features/conversation/components/ConversationStatusBadge.tsx`

**Current (lines 25-28):**
```tsx
with_research: {
  label: "With Research",
  className: "bg-sky-500/15 text-sky-400 border border-sky-500/30",
},
```

**Option A - "Researched" (Recommended):**
```tsx
with_research: {
  label: "Researched",
  className: "bg-sky-500/15 text-sky-400 border border-sky-500/30",
},
```

**Option B - "Active":**
```tsx
with_research: {
  label: "Active",
  className: "bg-sky-500/15 text-sky-400 border border-sky-500/30",
},
```

### Implementation Note
If changing the label, also update the JSDoc comment in the file (lines 5-9 and 34-38) to match:
- Line 8: "with_research": Conversation with research runs" -> description should match new label

---

## Final Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Clarity | Good | Both labels are understandable |
| Brevity | Good | Appropriate for small badge size |
| Consistency | Fair | "Draft" aligns well; "With Research" breaks single-word pattern |
| Accessibility | Excellent | Text labels, good contrast, no aria needed |
| User Understanding | Good | Technical users will understand; new users may need context |

**Overall Copy Quality:** 7/10 - Functional and clear, with minor consistency opportunity.

---

**APPROVAL REQUIRED**

Please review the copy analysis. Reply with:

- **"proceed"** or **"yes"** - Change "With Research" to "Researched" for consistency
- **"keep"** - Keep current copy as-is (acceptable for MVP)
- **"alternative: [label]"** - Use a different label (e.g., "alternative: Active")
- **"elaborate"** - Provide more details about specific suggestions
- **"skip"** - Skip copy review, no changes needed

**Key Question:** Do you prefer:
- A) "Researched" (single word, aligns with other status patterns)
- B) "With Research" (current, explicit but inconsistent)
- C) Different label (specify)

Waiting for your approval...
