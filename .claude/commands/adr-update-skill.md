---
description: Update skill for codebase drift or improvements
argument-hint: [skill-name]
model: sonnet
allowed-tools: Read, Write, Glob, Grep, Bash(ls:*), Bash(grep:*), AskUserQuestion, Task
---

# Update Skill

Update an existing skill when the codebase has drifted or better procedures have been discovered.

## Skill Name
$ARGUMENTS

## When to Use

- File paths in skill have changed
- Line number references are stale
- APIs or patterns the skill references have evolved
- Better procedures discovered through usage
- Skill needs clarification or refinement

---

## Process

### Step 1: Skill Selection

**If argument provided:**

```bash
# Validate skill exists (check both locations)
ls .claude/skills/adr-$ARGUMENTS/SKILL.md skills/adr-$ARGUMENTS/SKILL.md 2>/dev/null
```

**If no argument or skill not found:**

First, list available skills:

```bash
# List all skills
ls .claude/skills/*/SKILL.md skills/*/SKILL.md 2>/dev/null | sed 's|.*/\(adr-[^/]*\)/.*|\1|' | sort -u
```

Then use AskUserQuestion to let user select:

```
Question:
  header: "Select Skill"
  question: "Which skill do you want to update?"
  options:
    - label: "{skill-1-name}"
      description: "{skill-1-description from _index.md}"
    - label: "{skill-2-name}"
      description: "{skill-2-description from _index.md}"
    [dynamically generated from skill list]
  multiSelect: false
```

---

### Step 2: Load Current Skill

Read the skill files:
- SKILL.md (primary)
- patterns.md (if exists)

Extract and summarize:
- Frontmatter (description, tools)
- "When to Use" triggers
- Process steps (count and summary)
- File:line references found
- Anti-patterns

**Present summary:**

```markdown
## Current Skill: {skill-name}

### Description
{from frontmatter}

### Process
{count} steps

### File References Found
| Reference | Line in SKILL.md |
|-----------|------------------|
| `src/path/file.ts:45` | 28 |
```

---

### Step 3: Update Type Selection

**Use AskUserQuestion:**

```
Question:
  header: "Update Type"
  question: "What kind of update is needed?"
  options:
    - label: "Codebase drift"
      description: "File paths, APIs, or patterns have changed - re-research references"
    - label: "Skill improvement"
      description: "Better procedures discovered - revise steps or anti-patterns"
    - label: "Both"
      description: "Update references AND improve procedures"
  multiSelect: false
```

---

### Step 4: Context Gathering

**For "Codebase drift":**

Use Task tool with adr-research-agent to find current references:

```
Prompt to research agent:
"Find current locations of these patterns in the codebase:
- {pattern 1 from skill}
- {pattern 2 from skill}

The skill references these files which may have moved or changed:
- {file reference 1}
- {file reference 2}

Return file:line references for the current locations."
```

**For "Skill improvement":**

Use AskUserQuestion:

```
Question:
  header: "Improvement"
  question: "What improvement should be made?"
  options:
    - label: "Add step"
      description: "Insert a new step in the process"
    - label: "Revise step"
      description: "Improve an existing step"
    - label: "Add anti-pattern"
      description: "Document a mistake to avoid"
    - label: "Clarify triggers"
      description: "Refine 'When to Use' section"
  multiSelect: true
```

Then ask for details via follow-up or "Other" input.

---

### Step 5: Generate and Preview Changes

Create diff-style preview:

```markdown
## Changes Preview: {skill-name}

### SKILL.md Changes

#### Section: Process > Step 2
- Read `src/api/route.ts:45-60`
+ Read `src/api/handlers/route.ts:67-82`

#### Section: Anti-Patterns
+ - Don't use deprecated fetchData, use fetchDataV2
```

---

### Step 6: Confirmation

**Use AskUserQuestion:**

```
Question:
  header: "Confirm"
  question: "How would you like to proceed with these changes?"
  options:
    - label: "Apply changes (Recommended)"
      description: "Update the skill files as shown"
    - label: "Edit first"
      description: "Modify the changes before applying"
    - label: "Cancel"
      description: "Discard without updating"
  multiSelect: false
```

---

### Step 7: Apply Updates

Write updated files:
1. Update SKILL.md with changes
2. Update patterns.md if needed
3. Update _index.md if description changed

---

## Output

```markdown
## Skill Updated: {skill-name}

### Changes Applied
- **SKILL.md**: {count} sections updated
- **patterns.md**: {updated/no changes}
- **_index.md**: {updated/no changes}

### Reference Updates
| Original | Updated |
|----------|---------|
| `old/path:line` | `new/path:line` |

### Procedure Changes
- {summary if any}

### Verification
The skill has been updated. Changes are unstaged - review and commit when ready.
```

## Quality Checklist

Before completing:
- [ ] All file:line references verified current
- [ ] Skill still follows SKILL.md template
- [ ] Process steps are still numbered correctly
- [ ] Anti-patterns are still relevant
- [ ] Token budget maintained (~500 tokens for SKILL.md)
