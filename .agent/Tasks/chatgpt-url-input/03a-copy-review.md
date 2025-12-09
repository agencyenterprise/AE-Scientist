# Copy Review: ChatGPT & Grok URL Input Component

## Agent
copy-reviewer

## Timestamp
2025-12-08 15:30

## Files Reviewed
| File | Copy Elements Found |
|------|---------------------|
| `frontend/src/features/input-pipeline/components/ChatGptUrlInput.tsx` | Label, helper text, placeholder, default helper text, extracting state message |
| `frontend/src/features/input-pipeline/components/HypothesisForm.tsx` | Field labels, placeholders (for context) |
| `frontend/src/features/input-pipeline/components/CreateHypothesisForm.tsx` | Button text, error messages (for context) |

## Brand Voice Check
- Guidelines found: No (`.agent/System/brand-voice.md` and `.agent/System/copy-guidelines.md` do not exist)
- Compliance: N/A - Reviewed against codebase patterns and UX writing best practices

## Codebase Consistency Reference
Reviewed the following for existing patterns:
- `HypothesisForm.tsx`: "Hypothesis title", "Hypothesis details"
- `CreateHypothesisForm.tsx`: "Create hypothesis", "Generating...", "or" divider
- `ImportStreamingCard.tsx`: "Importing Conversation", "Updating Conversation", "Analyzing conversation and generating research hypothesis..."

---

## Summary

The ChatGptUrlInput component copy is mostly clear and functional. The main issues are **inconsistent terminology** ("share link" vs "conversation URL" vs "shared conversation URL") and a **lengthy extracting message** that could be more concise. There's also an opportunity to improve accessibility and provide clearer guidance about what happens next.

---

## Findings

### Must Fix (Clarity/Accessibility Issues)

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| Line 60 | "Paste ChatGPT or Grok share link" | Inconsistent with helper text (line 102) which says "conversation URL". Also, "share link" is less precise than "shared link". | "Paste ChatGPT or Grok shared link" OR "ChatGPT or Grok conversation URL" |
| Line 81 | No placeholder format validation hint | Placeholder shows two URLs but doesn't indicate both formats are valid or what makes a valid URL | "https://chatgpt.com/share/... or https://x.com/i/grok/share/..." (add "/share/" to Grok example for clarity) |
| Line 98-99 | "Extracting the hypothesis from [ChatGPT/Grok] — this usually takes under 30 seconds. We'll spin up a new run as soon as it's ready." | Two issues: (1) "spin up a new run" is technical jargon; (2) message is very long for a helper text; (3) "ready" is ambiguous - ready for what? | "Extracting hypothesis from [ChatGPT/Grok]. This usually takes under 30 seconds." |

### Should Fix (Consistency/Tone Issues)

| Location | Current Copy | Issue | Suggested Fix |
|----------|--------------|-------|---------------|
| Line 63 | "We'll extract the title and summary automatically." | (1) Uses future tense "We'll" but extraction happens when user submits; (2) Says "title and summary" but form uses "title and details"; (3) Slightly misleading timing | "Automatically extracts title and details when you submit" OR "Title and details will be extracted from the conversation" |
| Line 102 | "Paste a shared ChatGPT or Grok conversation URL to automatically extract and structure your hypothesis." | (1) Redundant with label; (2) Says "shared...conversation URL" which is wordier than "shared conversation URL" or "share link"; (3) "structure your hypothesis" is vague | "Paste a ChatGPT or Grok share link to import the conversation as a hypothesis" |
| Line 81 | Placeholder uses "..." for truncation | Using "..." is common but could use ellipsis character "…" for consistency | Consider "https://chatgpt.com/share/…" (using actual ellipsis) or keep "..." as standard |

### Suggestions (Polish)

| Location | Current Copy | Suggestion | Rationale |
|----------|--------------|------------|-----------|
| Line 60 | "Paste ChatGPT or Grok share link" | Consider: "ChatGPT or Grok share link" (remove "Paste") | The action "paste" is redundant - it's an input field. The placeholder already suggests pasting. |
| Line 88-91 | "Extracting…" badge | Consider adding platform icon to badge | Since the message already shows which platform, could reinforce visually with the icon |
| Line 102 | Default helper text position | Consider moving most helpful info to right-side helper text (line 63) | Users look at labels/inline help first, not bottom text |
| General | "hypothesis" terminology | Clarify relationship between "hypothesis" and "conversation" | Component imports "conversation" but creates "hypothesis". Could be clearer that conversation → hypothesis. |

---

## Terminology Consistency Check

| Term | Usage in Component | Usage Elsewhere | Recommendation |
|------|-------------------|-----------------|----------------|
| share link | Label: "share link" | Not found elsewhere | Use "shared link" (more grammatically correct) |
| conversation URL | Helper text: "conversation URL" | `ImportStreamingCard`: "conversation" | INCONSISTENT - choose one term |
| shared conversation URL | Helper text: "shared...conversation URL" | Not found elsewhere | Too wordy |
| hypothesis | Extract message: "hypothesis" | `HypothesisForm`: "Hypothesis title" | CONSISTENT |
| run | "spin up a new run" | Research context uses "run" | Jargon for end users |

### Terminology Recommendation

**Option 1 (Recommended)**: Use "share link" consistently
- Label: "ChatGPT or Grok share link"
- Placeholder: "https://chatgpt.com/share/... or https://x.com/i/grok/share/..."
- Helper: "Paste a share link to import the conversation as a hypothesis"

**Option 2**: Use "conversation URL" consistently
- Label: "ChatGPT or Grok conversation URL"
- Placeholder: unchanged
- Helper: "Paste a conversation URL to extract and import as a hypothesis"

**Option 3**: Use "shared conversation link" (compromise)
- Label: "Shared ChatGPT or Grok conversation"
- More verbose but clearest

---

## Accessibility Audit

| Check | Status | Notes |
|-------|--------|-------|
| Label association | PASS | `htmlFor="chatgpt-url"` correctly associates with input `id="chatgpt-url"` |
| Helper text association | NEEDS WORK | Bottom helper text (line 95-103) not associated with input via `aria-describedby` |
| Platform icons | PASS | Icons are decorative (inside input), not clickable, don't need aria-label |
| Loading state | PASS | "Extracting…" badge with spinner is visible and clear |
| Error messages | PASS | Error state changes text color and displays error message |
| Input states | PASS | Disabled state properly communicated via `disabled` attribute |
| Placeholder clarity | NEEDS WORK | Placeholder could be clearer about URL format requirements |

---

## User Experience Flow Analysis

### Current Flow
1. User sees label: "Paste ChatGPT or Grok share link"
2. User sees right helper: "We'll extract the title and summary automatically."
3. User enters URL
4. User sees platform icon appear (ChatGPT = green MessageSquare, Grok = purple Sparkles)
5. User submits form
6. User sees "Extracting…" badge and message about 30 seconds and "spinning up run"

### Issues
1. **Timing confusion**: Right helper says "We'll extract" (future) but extraction happens after submit, not during typing
2. **Information overload**: Extracting message tries to communicate too much (what's happening + time estimate + what happens next)
3. **Technical jargon**: "spin up a new run" assumes user understands the system architecture
4. **No validation feedback**: Component detects platform but doesn't confirm "Valid ChatGPT URL detected" vs "Invalid URL"

### Suggested Flow Improvements
1. Label: States capability clearly
2. Right helper: Sets expectation about what gets extracted
3. Platform icon: Provides instant visual feedback that URL is recognized
4. Bottom helper: Explains the overall process (when idle)
5. Extracting message: Focuses on current action + time estimate only

---

## Detailed Copy Recommendations

### Recommended Copy (Priority: Must Fix)

#### Label (Line 60)
**Current**: `"Paste ChatGPT or Grok share link"`
**Recommended**: `"ChatGPT or Grok share link"`
**Rationale**: Remove redundant "Paste" - it's implied by the input field.

#### Placeholder (Line 81)
**Current**: `"https://chatgpt.com/share/... or https://x.com/i/grok/..."`
**Recommended**: `"https://chatgpt.com/share/... or https://x.com/i/grok/share/..."`
**Rationale**: Add "/share/" to Grok URL example to show the expected format more clearly. Current Grok pattern is too generic.

#### Extracting Message (Lines 98-99)
**Current**: `"Extracting the hypothesis from [ChatGPT/Grok] — this usually takes under 30 seconds. We'll spin up a new run as soon as it's ready."`
**Recommended**: `"Extracting conversation from [ChatGPT/Grok]. This usually takes under 30 seconds."`
**Rationale**:
- Remove jargon "spin up a new run"
- Focus on current action (extraction) not future action (run)
- "extracting the hypothesis" is incorrect - we're extracting the conversation, then converting to hypothesis
- More concise for better scannability

### Recommended Copy (Priority: Should Fix)

#### Right Helper Text (Line 63)
**Current**: `"We'll extract the title and summary automatically."`
**Recommended**: `"Extracts conversation title and details automatically"`
**Rationale**:
- Present tense (extracts) vs future (we'll extract) - more accurate
- "details" matches `HypothesisForm` terminology (uses "Hypothesis details" not "summary")
- Remove "We" for more concise, professional tone
- Remove period for consistency with label style

#### Bottom Helper Text (Line 102)
**Current**: `"Paste a shared ChatGPT or Grok conversation URL to automatically extract and structure your hypothesis."`
**Recommended**: `"Paste a share link to import the conversation as a research hypothesis"`
**Rationale**:
- Shorter, more direct
- "import...as" is clearer transformation than "extract and structure"
- "research hypothesis" connects to the broader research workflow
- Matches "Create hypothesis" button terminology

### Accessibility Enhancement

Add `aria-describedby` to input (Line 79-86):
```tsx
<input
  id="chatgpt-url"
  aria-describedby="chatgpt-url-help"
  // ... other props
/>
```

And add id to helper text (Line 95):
```tsx
<p
  id="chatgpt-url-help"
  className={...}
>
```

---

## Side-by-Side Comparison

### Label
| Current | Recommended | Change Type |
|---------|-------------|-------------|
| "Paste ChatGPT or Grok share link" | "ChatGPT or Grok share link" | Must Fix |

### Right Helper
| Current | Recommended | Change Type |
|---------|-------------|-------------|
| "We'll extract the title and summary automatically." | "Extracts conversation title and details automatically" | Should Fix |

### Placeholder
| Current | Recommended | Change Type |
|---------|-------------|-------------|
| "https://chatgpt.com/share/... or https://x.com/i/grok/..." | "https://chatgpt.com/share/... or https://x.com/i/grok/share/..." | Must Fix |

### Bottom Helper (Default State)
| Current | Recommended | Change Type |
|---------|-------------|-------------|
| "Paste a shared ChatGPT or Grok conversation URL to automatically extract and structure your hypothesis." | "Paste a share link to import the conversation as a research hypothesis" | Should Fix |

### Bottom Helper (Extracting State)
| Current | Recommended | Change Type |
|---------|-------------|-------------|
| "Extracting the hypothesis from [ChatGPT/Grok] — this usually takes under 30 seconds. We'll spin up a new run as soon as it's ready." | "Extracting conversation from [ChatGPT/Grok]. This usually takes under 30 seconds." | Must Fix |

---

## Priority Summary

| Category | Count | Items |
|----------|-------|-------|
| Must Fix | 3 | Label, Placeholder, Extracting message |
| Should Fix | 2 | Right helper, Bottom helper |
| Accessibility | 1 | Add aria-describedby |
| Suggestions | 4 | Optional polish improvements |

---

## Code Changes Required

### File: `frontend/src/features/input-pipeline/components/ChatGptUrlInput.tsx`

**Line 60** - Label:
```tsx
// Before:
Paste ChatGPT or Grok share link

// After:
ChatGPT or Grok share link
```

**Line 63** - Right helper text:
```tsx
// Before:
We&apos;ll extract the title and summary automatically.

// After:
Extracts conversation title and details automatically
```

**Line 79-86** - Input (add aria-describedby):
```tsx
// Before:
<input
  id="chatgpt-url"
  placeholder="https://chatgpt.com/share/... or https://x.com/i/grok/..."
  // ...

// After:
<input
  id="chatgpt-url"
  aria-describedby="chatgpt-url-help"
  placeholder="https://chatgpt.com/share/... or https://x.com/i/grok/share/..."
  // ...
```

**Line 95** - Helper text container (add id):
```tsx
// Before:
<p
  className={`mt-2 text-xs ${isExtracting ? "text-sky-200" : error ? "text-rose-400" : "text-slate-500"}`}
>

// After:
<p
  id="chatgpt-url-help"
  className={`mt-2 text-xs ${isExtracting ? "text-sky-200" : error ? "text-rose-400" : "text-slate-500"}`}
>
```

**Lines 98-99** - Extracting message:
```tsx
// Before:
? `Extracting the hypothesis from ${platform === "grok" ? "Grok" : "ChatGPT"} — this usually takes under 30 seconds. We'll spin up a new run as soon as it's ready.`

// After:
? `Extracting conversation from ${platform === "grok" ? "Grok" : "ChatGPT"}. This usually takes under 30 seconds.`
```

**Line 102** - Default helper text:
```tsx
// Before:
: "Paste a shared ChatGPT or Grok conversation URL to automatically extract and structure your hypothesis."}

// After:
: "Paste a share link to import the conversation as a research hypothesis"}
```

---

## For Executor

Apply these changes to `frontend/src/features/input-pipeline/components/ChatGptUrlInput.tsx`:

### Priority 1 (Must Fix - Lines 60, 81, 98-99, 102)
1. **Line 60**: Remove "Paste" from label
2. **Line 81**: Add "/share/" to Grok placeholder URL example
3. **Lines 98-99**: Simplify extracting message, remove jargon
4. **Line 102**: Simplify default helper text

### Priority 2 (Should Fix - Line 63)
5. **Line 63**: Update right helper text to match form terminology

### Priority 3 (Accessibility - Lines 81, 95)
6. **Line 81**: Add `aria-describedby="chatgpt-url-help"` to input
7. **Line 95**: Add `id="chatgpt-url-help"` to helper text paragraph

---

## APPROVAL REQUIRED

Please review the copy suggestions. Reply with:
- **"proceed"** or **"yes"** - Apply all recommended fixes (Must Fix + Should Fix + Accessibility)
- **"must-fix-only"** - Apply only the 3 Must Fix items
- **"apply: [specific items]"** - Apply only certain fixes (e.g., "apply: 1, 2, 3, 6, 7")
- **"elaborate"** - Provide more details about specific suggestions
- **"modify: [feedback]"** - Adjust recommendations based on your feedback
- **"skip"** - Skip copy fixes for now

**Terminology Decision Needed**: Should we standardize on:
1. "share link" (shorter, matches actual URL path)
2. "conversation URL" (more descriptive)
3. "shared conversation link" (clearest but wordiest)

Current recommendation uses "share link" throughout.

Waiting for your approval...
