# Copy Review

## Agent
copy-reviewer

## Timestamp
2025-12-08 18:30

## Files Reviewed
| File | Copy Elements Found |
|------|---------------------|
| IdeationQueueCard.tsx | Edit button label, aria-label, expand/collapse button text |
| InlineIdeaView.tsx | Edit button label, empty state headings, error messages |
| conversations.py (models) | Status field API description |

## Brand Voice Check
- Guidelines found: No (no brand-voice.md or copy-guidelines.md exists)
- Compliance: N/A - Following codebase conventions instead

---

## Findings

### 🔴 Must Fix (Clarity/Accessibility Issues)

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| InlineIdeaView.tsx:108-116 | Button has no aria-label | Accessibility: Icon+text button navigating to different page should have aria-label for screen readers | Add `aria-label="Edit research idea"` to match IdeationQueueCard pattern |

### 🟡 Should Fix (Consistency/Tone Issues)

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| IdeationQueueCard.tsx:84 | `aria-label="Edit conversation"` | Inconsistent terminology: Button navigates to conversation page, but InlineIdeaView shows "idea" content. Need consistent terminology. | Consider standardizing: either both say "conversation" or both say "research idea" |
| IdeationQueueCard.tsx:87 | `Edit` | Button text is correct but context unclear - edit what? | Consider "Edit idea" for clarity, or keep "Edit" if space constrained (current is acceptable) |
| InlineIdeaView.tsx:115 | `Edit` | Same as above - button text is correct but doesn't specify what will be edited | Consider "Edit idea" for clarity (current is acceptable) |

### 🟢 Minor Suggestions (Polish)

| Location | Current Copy | Suggestion |
|----------|--------------|------------|
| conversations.py:108-111 | `"Conversation status: 'draft' (initial) or 'with_research' (has research runs)"` | Good API documentation. Consider simplifying to: `"Status: 'draft' for new conversations, 'with_research' when research has been launched"` |
| IdeationQueueCard.tsx:101 | `"Hide Runs"` / `"Show Runs"` | Could be more descriptive: `"Hide research runs"` / `"Show research runs"` - but current is acceptable given space constraints |
| InlineIdeaView.tsx:35 | `"Select an idea"` | Clear and actionable - good! |
| InlineIdeaView.tsx:36 | `"Click on an idea above to preview its details"` | Assumes mouse interaction. Consider: `"Choose an idea above to preview its details"` for device-agnostic language |
| InlineIdeaView.tsx:65 | `"No idea yet"` | Clear empty state |
| InlineIdeaView.tsx:66-68 | `"This conversation doesn't have an idea generated yet"` | Clear explanation - good! |

---

## Terminology Consistency Check

| Term | Used As | Files | Recommendation |
|------|---------|-------|----------------|
| conversation | aria-label | IdeationQueueCard.tsx:84 | Used in aria-label "Edit conversation" |
| idea | Heading, copy | InlineIdeaView.tsx:35, 65, 67 | Used in empty states "Select an idea", "No idea yet" |
| research runs | Badge, toggle | InlineIdeaView.tsx:102, IdeationQueueCard.tsx:93 | Consistent usage |

**Analysis**: The codebase uses "conversation" to refer to the data container and "idea" to refer to the generated research idea within it. The Edit buttons navigate to `/conversations/{id}` page, so "Edit conversation" in aria-label is technically accurate. However, the visual context shows "idea" content. This is acceptable given the data model distinction.

## Accessibility Audit

| Check | Status | Notes |
|-------|--------|-------|
| Button labels | 🔴 | IdeationQueueCard has aria-label, InlineIdeaView missing |
| Error messages | ✅ | Error state in InlineIdeaView explains problem and has "Try again" action |
| Form labels | N/A | No forms in reviewed components |
| Empty states | ✅ | Clear, actionable empty states in InlineIdeaView |
| Expand/collapse | ✅ | Has aria-label and aria-expanded attributes |

## Summary

| Category | Count |
|----------|-------|
| 🔴 Must Fix | 1 |
| 🟡 Should Fix | 3 |
| 🟢 Suggestions | 4 |

## For Executor
Apply these fixes:

1. **[MUST FIX]** Add aria-label to InlineIdeaView Edit button:
   ```tsx
   // In InlineIdeaView.tsx, line 108-116
   <Button
     onClick={handleEditClick}
     variant="outline"
     size="sm"
     className="ml-auto"
     aria-label="Edit research idea"  // ADD THIS
   >
     <Pencil className="h-3 w-3 mr-1.5" />
     Edit
   </Button>
   ```

2. **[OPTIONAL - Consistency]** If desired, update IdeationQueueCard aria-label to match:
   - Current: `aria-label="Edit conversation"`
   - Option: `aria-label="Edit research idea"` for consistency with InlineIdeaView

3. **[OPTIONAL - Polish]** Update InlineIdeaView empty state for device-agnostic language:
   - Current: "Click on an idea above to preview its details"
   - Suggested: "Choose an idea above to preview its details"

---

**APPROVAL REQUIRED**

Please review the copy suggestions. Reply with:
- **"proceed"** or **"yes"** - Apply the must-fix (aria-label)
- **"proceed all"** - Apply all suggestions including optional ones
- **"modify: [feedback]"** - Adjust recommendations
- **"elaborate"** - Provide more details about the suggestions
- **"skip"** - Skip copy fixes for now

Waiting for your approval...
