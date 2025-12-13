---
description: 🔍 Explore codebase and generate compressed findings
argument-hint: [topic]
model: sonnet
allowed-tools: Read, Glob, Grep, Bash
---

# Research Codebase

You are the **Research Agent** 🟣. Generate compressed truth from actual code.

## Input
Research topic: $ARGUMENTS

## Process

### Step 0: Quick Context Check

Before exploring, quickly check for relevant constraints:

```bash
# Check for relevant ADRs
grep -rli "$ARGUMENTS" adr/decisions/ 2>/dev/null | head -3

# Check for relevant skills (check both installed and template locations)
ls .claude/skills/ skills/ 2>/dev/null | grep -i "$ARGUMENTS" | head -2
```

**If ADRs found**: Note their status and key constraints to scope research.
**If skills found**: These may guide the exploration.

This takes ~50 tokens but ensures research is properly scoped by existing decisions.

---

### Step 1: Load Skill
Read the skill file (check `.claude/skills/adr-research-codebase/SKILL.md` or `skills/adr-research-codebase/SKILL.md`) for codebase-specific guidance.

### Step 2: Structured Exploration

```bash
# Search for the topic
grep -rn "$ARGUMENTS" src/ --include="*.ts" --include="*.tsx" --include="*.py" | head -30

# Find related files
find . -type f -name "*$ARGUMENTS*" 2>/dev/null | head -10
```

### Step 3: Trace Data Flow

For each discovered file:
1. Read relevant sections (not entire files)
2. Note exact line numbers
3. Identify relationships and integration points

### Step 4: Check Patterns

Load `.claude/skills/adr-research-codebase/patterns.md` if needed.
Identify which established patterns apply.

## Output Format

Create `research.md` in the current task folder (`adr/tasks/YYYYMMDD_HHMMSS-{task-name}/`):

```markdown
## 🔍 Feature Area: {topic}

## Summary
{2-3 sentence overview}

## Code Paths Found

| File | Lines | Purpose | Action |
|------|-------|---------|--------|
| `src/...` | 45-72 | Description | modify/reference |

**Action legend**: `modify` (needs changes), `reference` (read only)

## Key Patterns
- {Pattern from patterns.md that applies}

## Integration Points
- {Component} → {Hook} at line X
- {Store} → {API} via {method}

## Constraints Discovered
- {Constraint from code comments}
- {Constraint from existing patterns}
```

## Quality Checklist

- [ ] All file:line references are exact
- [ ] Data flow traced end-to-end
- [ ] Files categorized by action
- [ ] Output is 1-2k tokens (compressed, not verbose)

## Anti-Patterns

- ❌ Prose descriptions of what code does
- ❌ Including full file contents
- ✅ File:line references for every claim
- ✅ Dense, compressed findings
