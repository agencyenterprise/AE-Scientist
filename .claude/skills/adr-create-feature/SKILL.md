---
description: Standard feature implementation with research-plan-execute workflow
tools: Read, Write, Edit, Bash, Glob, Grep, Task
---

# ADR Create Feature Skill

## When to Use
- Implementing new features
- Adding functionality to existing code
- Multi-file changes that need coordination

## Workflow Overview

```
Research 🟣 → Plan 🔵 → Execute 🟢
    │           │           │
    ▼           ▼           ▼
research.md   plan.md    code changes
    │           │           │
    └─── Human Review ──────┘
```

## Process

### Phase 1: Research (🟣 adr-research-agent)

```
Use the adr-research-agent to explore: "{feature description}"
```

**Output**: `research.md` with file:line references
**Checkpoint**: Human reviews understanding

### Phase 2: Plan (🔵 adr-planner-agent)

```
Use the adr-planner-agent to create implementation plan
```

**Output**: `plan.md` with before/after code
**Checkpoint**: Human reviews plan ⭐ HIGHEST LEVERAGE

### Phase 3: Execute (🟢 adr-executor-agent)

```
Use the adr-executor-agent to implement plan.md
```

**Input**: ONLY plan.md (fresh context)
**Output**: Working code with tests passing

## Quality Gates

### Research Quality
- [ ] All file references include line numbers
- [ ] Data flow traced end-to-end
- [ ] Existing patterns identified

### Plan Quality
- [ ] Before/after code for each change
- [ ] Steps in correct dependency order
- [ ] Self-contained (no external context needed)

### Execution Quality
- [ ] All plan steps completed
- [ ] Tests passing
- [ ] No TypeScript errors
- [ ] No lint errors

## Checklist Template

For feature `{name}`:

```markdown
## Feature: {name}

### Research
- [ ] Identified affected files
- [ ] Traced data flow
- [ ] Found existing patterns
- [ ] research.md created

### Plan
- [ ] Before/after for each change
- [ ] Correct step ordering
- [ ] plan.md approved

### Execute
- [ ] All steps completed
- [ ] Tests passing
- [ ] Types check
- [ ] Lint clean

### Wrap-up
- [ ] Commit with descriptive message
- [ ] Update docs if needed
- [ ] Consider: Is this a reusable pattern? → /save-skill
```

## Anti-Patterns

- ❌ Skipping research phase
- ❌ Vague plans without line numbers
- ❌ Executing without plan approval
- ❌ Keeping conversation context for execution

- ✅ Research → Plan → Execute in order
- ✅ Human checkpoint at each phase
- ✅ Fresh context for executor
- ✅ Plan is the contract
