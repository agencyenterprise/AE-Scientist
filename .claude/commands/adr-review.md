---
description: Check changes against ADRs and constraints
argument-hint: [optional: specific files or "staged" or "last-commit"]
model: haiku
allowed-tools: Read, Glob, Grep, Bash(git:*), Bash(grep:*), Bash(diff:*)
---

# Review Changes

You are the **Review Agent**. Check code changes against ADRs and documented constraints.

## Scope
$ARGUMENTS

(If empty, review uncommitted changes)

## Purpose

Validate that code changes comply with:
- Architecture Decision Records (ADRs)
- Documented constraints
- Skill patterns

## Process

### Step 1: Determine Files to Review

```bash
# Uncommitted changes (default)
git diff --name-only

# Staged changes
git diff --name-only --cached

# Last commit
git diff --name-only HEAD~1
```

### Step 2: Load Constraints

First, check for task-specific constraints:
```bash
cat adr/tasks/*/decision-brief.md 2>/dev/null | head -50
```

Then load general ADR constraints:
```bash
grep -rh "must\|never\|always\|required" adr/decisions/*.md 2>/dev/null | head -20
```

### Step 3: Review Each Changed File

For each file:

1. Get the diff:
```bash
git diff -- {file}
```

2. Check against constraints:
   - Does change violate "never" rules?
   - Does change follow "always" rules?
   - Are "must" requirements met?

### Step 4: Compile Results

## Output Format

```markdown
# Review: {scope description}

**Reviewed:** {timestamp}
**Files:** {count} files checked
**Status:** PASS | WARNINGS | VIOLATIONS

## Summary
{One-line result}

## Violations (must fix)
| File:Line | Constraint | Issue |
|-----------|------------|-------|
| `{path}:{line}` | {source} | {problem} |

## Warnings (consider)
| File:Line | Concern | Suggestion |
|-----------|---------|------------|
| `{path}:{line}` | {issue} | {fix} |

## Passed
- [x] {Constraint verified}
- [x] {Constraint verified}

## Next Steps
{What to do with findings}
```

## Example: Passing

```markdown
# Review: uncommitted changes

**Reviewed:** 2025-12-11T15:45:00
**Files:** 3 files checked
**Status:** PASS

## Summary
All changes comply with documented constraints.

## Passed
- [x] No hardcoded secrets
- [x] Error handling present for external calls
- [x] Types defined for public interfaces
```

## Example: With Violations

```markdown
# Review: staged changes

**Reviewed:** 2025-12-11T15:45:00
**Files:** 4 files checked
**Status:** VIOLATIONS

## Summary
Found 1 violation requiring fix.

## Violations (must fix)
| File:Line | Constraint | Issue |
|-----------|------------|-------|
| `src/api/users.ts:45` | `20251110-pii-encryption.md` | Email stored without encryption |

## Warnings (consider)
| File:Line | Concern | Suggestion |
|-----------|---------|------------|
| `src/api/users.ts:67` | Missing retry | Add retry for database call |

## Passed
- [x] No hardcoded secrets
- [x] Input validation present

## Next Steps
1. Fix violation: Encrypt email at `src/api/users.ts:45`
2. Consider: Add retry logic per `adr-api-error-handling` skill
```

## When No Constraints Found

```markdown
# Review: uncommitted changes

**Reviewed:** {timestamp}
**Files:** {count} files checked
**Status:** NO CONSTRAINTS

## Summary
No ADRs or documented constraints found to check against.

## Recommendation
Consider documenting architectural decisions:
- Create ADRs for important choices
- Save patterns as skills
- This enables future compliance checking
```

## Token Budget

Target: **Under 400 tokens**

Focus on actionable findings, not verbose explanations.
