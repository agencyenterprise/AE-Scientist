# Copy Review

## Agent
copy-reviewer

## Timestamp
2025-12-10 14:30

## Files Reviewed
| File | Copy Elements Found |
|------|---------------------|
| `conversation-filter-utils.ts` | Filter button labels (Conversation Status, Run Status) |
| `IdeationQueueHeader.tsx` | Section labels, ARIA labels, search placeholder |
| `ConversationStatusBadge.tsx` | Status badge labels (existing pattern reference) |
| `ideation-queue-utils.tsx` | Existing status labels (existing pattern reference) |

## Brand Voice Check
- Guidelines found: No
- Compliance: N/A - establishing patterns from existing code

---

## Findings

### Consistency Issue Found

**Critical Discovery**: There is a terminology inconsistency between:
- **Filter label**: "With Research" (in `conversation-filter-utils.ts`)
- **Badge label**: "Researched" (in `ConversationStatusBadge.tsx`)

These refer to the same status but use different terminology.

---

### Issues Identified

#### Issue 1: Inconsistent "With Research" vs "Researched" Terminology

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| `conversation-filter-utils.ts:8` | "With Research" | Inconsistent with badge label "Researched" | Align to "Researched" |

**Analysis**:
- The badge component (ConversationStatusBadge.tsx) uses "Researched" (past tense, concise)
- The filter uses "With Research" (wordy, different terminology)
- "Researched" is better: shorter, consistent with badge, more natural

**Recommendation**: Change filter label from "With Research" to "Researched"

---

### Copy That Is Working Well

| Location | Copy | Why It Works |
|----------|------|--------------|
| Filter labels | "All", "Draft" | Clear, concise, consistent |
| Run Status labels | "Pending", "Running", "Completed", "Failed" | Consistent with existing patterns in `ideation-queue-utils.tsx` |
| ARIA labels | "Filter by conversation status", "Filter by run status" | Clear, descriptive for screen readers |
| Section labels | "Conversation Status", "Run Status" | Clear grouping, appropriate capitalization |
| Search | "Search ideas...", aria-label="Search ideas" | Consistent placeholder and ARIA |

---

## Terminology Consistency Check

| Term | Filter Utils | Badge | Recommendation |
|------|--------------|-------|----------------|
| Draft | "Draft" | "Draft" | Consistent - no change |
| Researched status | "With Research" | "Researched" | Align to "Researched" |

| Term | New Filter Utils | Existing Ideation Utils | Consistent? |
|------|------------------|-------------------------|-------------|
| Pending | "Pending" | "Pending" | Yes |
| Running | "Running" | "Running" | Yes |
| Completed | "Completed" | "Completed" | Yes |
| Failed | "Failed" | "Failed" | Yes |

---

## Accessibility Audit

| Check | Status | Notes |
|-------|--------|-------|
| Filter group ARIA | Pass | `role="group"` with descriptive `aria-label` |
| Button states | Pass | `aria-pressed` correctly used for toggle buttons |
| Search input | Pass | Has both `aria-label` and `placeholder` |
| Section labels | Pass | `<label>` elements used for filter groups |

---

## Summary

| Category | Count |
|----------|-------|
| Must Fix | 1 |
| Should Fix | 0 |
| Suggestions | 0 |

The copy is generally well-written and follows accessibility best practices. The single issue is the terminology inconsistency between filter and badge labels.

---

## Recommended Fix

**File**: `/Users/jarbasmoraes/code/ae/ae-scientist/AE-Scientist/frontend/src/features/conversation/utils/conversation-filter-utils.ts`

**Line 8**: Change `label: 'With Research'` to `label: 'Researched'`

This aligns the filter terminology with the existing badge terminology in `ConversationStatusBadge.tsx`.

---

## APPROVAL REQUIRED

Please review the copy suggestion. Reply with:
- **"proceed"** or **"yes"** - Apply the fix (change "With Research" to "Researched")
- **"keep"** - Keep "With Research" as-is
- **"elaborate"** - Provide more details about the reasoning

Waiting for your approval...
