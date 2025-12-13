---
description: ⚡ Full workflow - Context → Research → Plan → Execute → Review
argument-hint: [feature description]
model: opus
allowed-tools: Read, Glob, Grep, Bash, Write, Edit, Task, AskUserQuestion
---

# Feature Implementation Workflow

Execute the full Context → Research → Plan → Execute → Review workflow.

## Feature Request
$ARGUMENTS

## Workflow

### Phase 0: Decision Context

**Gather historical context before starting:**

First, create task folder:
```bash
mkdir -p adr/tasks/$(date +%Y%m%d_%H%M%S)-{feature-slug}/
```

Then gather decision context:
```
Use the adr-decision-support-agent to gather context for: "$ARGUMENTS"
```

Output: `decision-brief.md` in task folder

**Review surfaced context:**
- Are there ADRs that constrain this work?
- Are there skills to apply?
- Is there similar past work to reference?

This context will guide research and planning.

---

### Phase 0.5: UX Strategy 🎨 (if frontend work)

**Trigger**: If feature description contains frontend keywords:
- ui, dashboard, page, form, component, layout, modal
- sidebar, navigation, header, footer, button, input
- table, list, card, notification, toast, dropdown

**Delegate to ux-strategy-agent:**

```
Use the ux-strategy-agent for UX guidance on: "$ARGUMENTS"
```

The agent will:
1. Ask 5 essential questions (JTBD, user type, complexity, assumption, craft)
2. Apply AE design principles
3. Output `ux-strategy.md` with layout, hierarchy, recommendations

**Human checkpoint - use AskUserQuestion:**

```
Question:
  header: "UX Review"
  question: "Does this UX direction match your vision?"
  options:
    - label: "Approved"
      description: "Continue to Research phase"
    - label: "Modify"
      description: "Adjust recommendations before proceeding"
    - label: "Skip"
      description: "Continue without UX strategy"
  multiSelect: false
```

Output: `ux-strategy.md` in task folder (passed to planner)

---

### Phase 1: Research 🟣

**Delegate to adr-research-agent subagent:**

```
Use the adr-research-agent to explore: "$ARGUMENTS"
Context: Reference decision-brief.md for constraints and relevant ADRs
```

Wait for research.md output.

**Human checkpoint - use AskUserQuestion:**

```
Question:
  header: "Research"
  question: "Does the research correctly understand the system?"
  options:
    - label: "Approved"
      description: "Research is accurate, continue to Planning"
    - label: "Adjust"
      description: "Re-run research with corrections"
  multiSelect: false
```

---

### Phase 2: Planning 🔵

**Delegate to adr-planner-agent subagent:**

```
Use the adr-planner-agent to create implementation plan based on research.md
If ux-strategy.md exists, include it as input for design guidance.
```

Wait for plan.md output.

**Human checkpoint** ⭐ **HIGHEST LEVERAGE - use AskUserQuestion:**

Review checklist:
- Are file:line references correct?
- Do before/after snippets make sense?
- Is implementation order logical?
- Are edge cases handled?

```
Question:
  header: "Plan"
  question: "Is this implementation plan ready to execute?"
  options:
    - label: "Approved (Recommended)"
      description: "Plan is correct, proceed to execution"
    - label: "Adjust"
      description: "Re-run planning with corrections"
  multiSelect: false
```

---

### Phase 3: Execution 🟢

**Critical: Fresh context with plan only**

**Delegate to adr-executor-agent subagent:**

```
Use the adr-executor-agent to implement plan.md
```

The executor receives ONLY plan.md — no conversation history.
This ensures:
- No poisoned trajectory
- Plan is the contract
- Maximum context for implementation

---

### Phase 4: Review 🔍

**Validate changes against constraints:**

```
Use the adr-review-agent to check changes against decision-brief.md
```

The review agent:
- Reads git diff of changes made
- Checks against constraints from decision-brief.md
- Reports violations or passes

**Review output:**
- **PASS** → Continue to completion
- **WARNINGS** → Consider fixes, then continue
- **VIOLATIONS** → Must fix before completing

---

## Output Summary

After all phases:

```markdown
## ⚡ Feature Complete: {name}

### Phases
- 🧠 Context: ✅ Gathered
- 🎨 UX Strategy: ✅ Approved (if frontend)
- 🟣 Research: ✅ Approved
- 🔵 Plan: ✅ Approved
- 🟢 Execute: ✅ Complete
- 🔍 Review: ✅ Passed

### Files Changed
- `{file}` — {change summary}

### Constraints Verified
- {constraint from decision-brief.md}

### Tests
- ✅ All tests passing

### Ready for PR
```

## Context Management

If context approaches 40% during any phase:
1. Complete current phase
2. Use `/adr-compact` to compress state
3. Resume with fresh context

## Novel Pattern?

If implementation reveals a reusable pattern:
```
/adr-save-skill {pattern-name}
```
