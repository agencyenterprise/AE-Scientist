---
description: 💾 Create skill from successful pattern
argument-hint: [skill-name]
model: sonnet
allowed-tools: Read, Write, Bash, AskUserQuestion
---

# Save Skill

Create a new skill from a successful pattern.

## Skill Name
$ARGUMENTS

## When to Use

- Just completed a task using a novel approach
- Found an efficient way to handle a recurring problem
- Want to preserve expertise for future use
- Team should follow a specific procedure

## Process

### Step 0: Duplicate Check

Before creating, check for existing similar skills:

```bash
# List existing skills (check both installed and template locations)
ls .claude/skills/ skills/ 2>/dev/null

# Search for similar content
grep -rli "$ARGUMENTS" .claude/skills/*/SKILL.md skills/*/SKILL.md 2>/dev/null
```

**If similar skill found, use AskUserQuestion:**

```
Question:
  header: "Duplicate"
  question: "Found existing skill: adr-{similar-name}. How to proceed?"
  options:
    - label: "Merge"
      description: "Add this pattern to the existing skill"
    - label: "Create new"
      description: "This has different scope, create separate skill"
    - label: "Cancel"
      description: "Use the existing skill instead"
  multiSelect: false
```

Only proceed if creating a genuinely new skill or extending an existing one.

---

### Step 1: Identify the Pattern

From recent work, extract:
- What was the repeatable procedure?
- What made it successful?
- What would you tell your future self?

### Step 2: Verify Skill Worthiness

**Good candidates:**
- ✅ Workflows that will be repeated
- ✅ Patterns specific to this codebase
- ✅ Scripts that automate common tasks
- ✅ Procedures that prevent mistakes

**Bad candidates:**
- ❌ Architecture descriptions (use ADRs)
- ❌ One-time procedures
- ❌ Generic knowledge Claude already has

### Step 3: Create Skill Structure

```bash
mkdir -p .claude/skills/adr-$ARGUMENTS
```

### Step 4: Write SKILL.md

```markdown
# {Skill Name}

## When to Use
{Clear trigger conditions}

## Process

### Step 1: {Action}
{Concrete instructions}

### Step 2: {Action}
{Instructions with examples}

## Tools
- `script.py <args>` — {description}

## Output Format
{What this skill produces}

## Anti-Patterns
- ❌ Don't do X
- ✅ Do Y instead
```

### Step 5: Extract Scripts (if applicable)

If reusable code was written, save as `.py` file in skill folder.

### Step 6: Update Skills Index

Add to `.claude/skills/_index.md`.

## Output

```markdown
## 💾 Skill Created: adr-{name}

### Location
`skills/adr-{name}/`

### Files
- ✅ SKILL.md — Entry point
- ✅ {scripts if any}

### Added to Index
✅ Updated `skills/_index.md`

### Usage
This skill will be available for future tasks.
Claude will activate it when the trigger conditions match.
```

## Continuous Learning Loop

```
Day 1:  Base skills from /adr-init
Day 7:  /adr-save-skill handle-api-errors
Day 14: /adr-save-skill setup-feature-flags
Day 30: Rich library of team expertise
        ↓
New team member → Inherits all accumulated skills
```
