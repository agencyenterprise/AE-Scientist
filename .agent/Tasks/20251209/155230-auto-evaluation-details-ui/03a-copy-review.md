# Copy Review - Auto Evaluation Details UI

## Agent
copy-reviewer

## Timestamp
2025-12-09 16:45 UTC

## Files Reviewed
| File | Copy Elements Found |
|------|---------------------|
| `/frontend/src/app/(dashboard)/research/[runId]/page.tsx` | Button text, loading state |
| `/frontend/src/features/research/components/run-detail/review/ReviewHeader.tsx` | Modal title, verdict badges |
| `/frontend/src/features/research/components/run-detail/review/ReviewTabs.tsx` | Tab labels |
| `/frontend/src/features/research/components/run-detail/review/ReviewScores.tsx` | Section title, metric labels |
| `/frontend/src/features/research/components/run-detail/review/ReviewAnalysis.tsx` | Section title, analysis labels, ethical concerns banner |
| `/frontend/src/features/research/components/run-detail/review/ReviewModal.tsx` | Loading text, error messages, not-found message |
| `/frontend/src/features/research/hooks/useReviewData.ts` | Error messages |

## Brand Voice Check
- Guidelines found: No (no brand-voice.md or copy-guidelines.md)
- Design guidelines found: Yes (design-guidelines.md)
- Compliance: Pass - Copy follows scientific/professional tone appropriate for a research platform

---

## Findings Summary

| Category | Count |
|----------|-------|
| Approved | 20 |
| Needs Improvement | 4 |
| Must Change | 1 |

---

## Detailed Review

### 1. Button Text (`page.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "View Auto Evaluation" | Line 124 | Needs Improvement | "Auto Evaluation" is internal terminology; users may not understand |
| "Loading..." | Line 124 | Approved | Clear and standard |

**Suggestion:**
```
Current: "View Auto Evaluation"
Suggested: "View Evaluation" or "View Review Details"
Reason: "Auto" prefix adds unnecessary technical detail. Users care about seeing the evaluation, not whether it was automated.
```

### 2. Modal Title (`ReviewHeader.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "Auto Evaluation Details" | Line 42 | Needs Improvement | Same issue as button - "Auto" is internal jargon |

**Suggestion:**
```
Current: "Auto Evaluation Details"
Suggested: "Evaluation Details" or "Review Details"
Reason: Simpler, cleaner title. The "Auto" prefix is implementation detail.
```

### 3. Verdict Badges (`ReviewHeader.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "PASS" | Line 17 | Approved | Clear, direct, appropriate for scientific context |
| "FAIL" | Line 21 | Approved | Clear, direct, appropriate for scientific context |

**Analysis:** PASS/FAIL are appropriate verdict labels for a research evaluation context. They are:
- Universally understood
- Direct and unambiguous
- Consistent with academic review conventions

### 4. Tab Labels (`ReviewTabs.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "Both" | Line 11 | Approved | Clear, indicates combined view |
| "Scores" | Line 12 | Approved | Matches section title, consistent |
| "Analysis" | Line 13 | Approved | Matches section title, consistent |

### 5. Section Titles (`ReviewScores.tsx`, `ReviewAnalysis.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "Quantitative Scores" | ReviewScores.tsx:46 | Approved | Professional, descriptive |
| "Qualitative Analysis" | ReviewAnalysis.tsx:146 | Approved | Professional, descriptive, pairs well with Quantitative |

**Note on Emojis:** The section titles include emojis (chart emoji and clipboard emoji). While emojis can reduce formality, they add visual hierarchy and scannability. For a dashboard UI, this is acceptable.

### 6. Metric Labels (`ReviewScores.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "Originality" | Line 16 | Approved | Standard academic review term |
| "Quality" | Line 17 | Approved | Standard academic review term |
| "Clarity" | Line 18 | Approved | Standard academic review term |
| "Significance" | Line 19 | Approved | Standard academic review term |
| "Soundness" | Line 20 | Approved | Standard academic review term |
| "Presentation" | Line 21 | Approved | Standard academic review term |
| "Contribution" | Line 22 | Approved | Standard academic review term |
| "Overall" | Line 23 | Approved | Standard academic review term |
| "Confidence" | Line 24 | Approved | Standard review term (reviewer confidence) |

**Analysis:** All metric names align with standard academic peer review terminology (as used in conferences like NeurIPS, ICML, etc.). No changes needed.

### 7. Analysis Section Labels (`ReviewAnalysis.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "Summary" | Line 68 | Approved | Standard, clear |
| "Strengths" | Line 78 | Approved | Standard review term |
| "Weaknesses" | Line 94 | Approved | Standard review term |
| "Questions" | Line 110 | Approved | Standard review term |
| "Limitations" | Line 125 | Approved | Standard review term |

### 8. Ethical Concerns Banner (`ReviewAnalysis.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "This review flagged ethical concerns" | Line 151 | Needs Improvement | Passive voice, lacks actionability |

**Suggestion:**
```
Current: "This review flagged ethical concerns"
Suggested: "Ethical concerns were identified in this research"
Alternative: "This evaluation identified ethical concerns"
Reason: More specific about what was evaluated. Consider adding guidance on what users should do.
```

### 9. Loading State (`ReviewModal.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "Loading evaluation..." | Line 86 | Approved | Clear, specific, uses ellipsis correctly |

### 10. Not Found State (`ReviewModal.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "No evaluation available for this run" | Line 107 | Approved | Clear, explains the situation |

### 11. Error Messages

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "Failed to load review" | useReviewData.ts:71 | Must Change | Generic, unhelpful |
| "Conversation ID is required" | useReviewData.ts:44 | Approved (internal) | Technical error, acceptable |
| "Run ID is required" | useReviewData.ts:49 | Approved (internal) | Technical error, acceptable |

**Suggestion:**
```
Current: "Failed to load review"
Suggested: "We couldn't load the evaluation. Please try again."
Reason: More helpful, suggests next action. Uses "we" to take responsibility.
```

### 12. Close Button (`ReviewModal.tsx`)

| Copy | Location | Verdict | Notes |
|------|----------|---------|-------|
| "Close" | Lines 98, 113 | Approved | Standard, clear |
| aria-label="Close modal" | ReviewHeader.tsx:57 | Approved | Good accessibility |

---

## Accessibility Audit

| Check | Status | Notes |
|-------|--------|-------|
| Button labels | Pass | "View Auto Evaluation" is descriptive |
| Close button aria-label | Pass | "Close modal" is present |
| Error messages | Pass | All explain the issue |
| Form labels | N/A | No forms in this feature |
| Link text | N/A | No links in this feature |
| Screen reader compatibility | Pass | Proper semantic HTML, visible text labels |

---

## Consistency Check

| Area | Status | Notes |
|------|--------|-------|
| Terminology | Warning | "Evaluation" vs "Review" used interchangeably |
| Capitalization | Pass | Sentence case for buttons, Title Case for headers |
| Tone | Pass | Professional, scientific throughout |

**Terminology Note:** The copy alternates between "Evaluation" and "Review":
- Button: "View Auto Evaluation"
- Modal title: "Auto Evaluation Details"
- Not found: "No evaluation available"
- Loading: "Loading evaluation"
- Error: "Failed to load review"

**Recommendation:** Standardize on "Evaluation" since it appears in user-facing UI elements and the feature name.

---

## Must Fix (1 issue)

| # | Location | Current | Suggested | Priority |
|---|----------|---------|-----------|----------|
| 1 | useReviewData.ts:71 | "Failed to load review" | "We couldn't load the evaluation. Please try again." | High |

---

## Should Fix (4 issues)

| # | Location | Current | Suggested | Priority |
|---|----------|---------|-----------|----------|
| 1 | page.tsx:124 | "View Auto Evaluation" | "View Evaluation" | Medium |
| 2 | ReviewHeader.tsx:42 | "Auto Evaluation Details" | "Evaluation Details" | Medium |
| 3 | ReviewAnalysis.tsx:151 | "This review flagged ethical concerns" | "Ethical concerns were identified in this research" | Medium |
| 4 | useReviewData.ts:71 | Uses "review" term | Change to "evaluation" for consistency | Low |

---

## Summary

The copy in this feature is generally clear, professional, and appropriate for a scientific research platform. The main issues are:

1. **Unnecessary jargon**: "Auto" prefix in "Auto Evaluation" adds no user value
2. **Minor inconsistency**: Alternating between "evaluation" and "review"
3. **One unhelpful error message**: Generic "Failed to load review"

All metric names and section labels follow academic review conventions correctly. Verdict badges (PASS/FAIL) are clear and appropriate. Accessibility is good with proper aria-labels.

---

## Approval Status

**APPROVAL REQUIRED**

Please review the copy suggestions above. Reply with:
- **"proceed"** or **"yes"** - Apply all suggested fixes
- **"apply: [specific fixes]"** - Apply only certain fixes (e.g., "apply: 1, 3")
- **"modify: [feedback]"** - Adjust recommendations
- **"elaborate"** - Provide more details about the suggestions
- **"skip"** - Skip copy fixes for now

Waiting for your approval...
