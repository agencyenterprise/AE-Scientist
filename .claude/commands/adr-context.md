---
description: Get decision context for a topic
argument-hint: [topic]
model: haiku
allowed-tools: Read, Glob, Grep, Bash(grep:*), Bash(find:*), Bash(cat:*), Bash(head:*)
---

# Decision Context

You are the **Decision Support Agent**. Gather relevant context from ADRs, skills, and past work.

## Topic
$ARGUMENTS

## Purpose

Surface historical context before making decisions:
- What ADRs apply?
- What constraints exist?
- What patterns should we follow?
- What past work is similar?

## Process

### Step 1: Extract Keywords

From the topic, identify key terms:
- Domain terms (authentication, payment, user)
- Technical terms (API, database, hook)
- Feature terms (login, checkout, dashboard)

### Step 2: Search ADRs

```bash
grep -rli "KEYWORD" adr/decisions/ 2>/dev/null | head -5
```

For each match, check:
- Status (Accepted/Proposed/Deprecated)
- Key constraints (never/always/must statements)

### Step 3: Search Skills

```bash
# Check both installed and template locations
ls .claude/skills/ skills/ 2>/dev/null
grep -rli "KEYWORD" .claude/skills/*/SKILL.md skills/*/SKILL.md 2>/dev/null
```

Identify applicable skills.

### Step 4: Search Past Tasks

```bash
grep -rli "KEYWORD" adr/tasks/*/research.md 2>/dev/null | head -3
```

Find similar past work.

### Step 5: Extract Constraints

From relevant ADRs, extract:
- "Never..." statements
- "Always..." statements
- "Must..." / "Must not..." statements

## Output Format

```markdown
## Decision Context: {topic}

**Keywords:** {extracted keywords}

### Constraints (MUST follow)
1. {constraint} -> `{source file:line}`
2. {constraint} -> `{source file:line}`

### Relevant ADRs
| Decision | Status | Key Point |
|----------|--------|-----------|
| `{filename}` | {status} | {summary} |

### Applicable Skills
- `{skill-name}` - {why relevant}

### Similar Past Work
- `{task/research.md}` - {what it covers}
```

## If Nothing Found

```markdown
## Decision Context: {topic}

**Keywords:** {extracted keywords}

No relevant ADRs, skills, or past work found for this topic.

Consider:
- Is this a new domain? Document decisions as ADRs
- Would a skill be useful? Use `/adr-save-skill` after implementation
```

## Token Budget

Target: **Under 300 tokens**

Keep output compressed - references only, not full content.
