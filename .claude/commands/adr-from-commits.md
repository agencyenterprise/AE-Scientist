---
description: 📝 Extract ADRs from commit history
argument-hint: [n|since-adr|interactive]
model: haiku
allowed-tools: Read, Glob, Grep, Bash(git:*), Write, Task, AskUserQuestion
---

# Extract ADRs from Commits

Extract architecture decisions from git commit history and create ADR files.

## Arguments
$ARGUMENTS

## Mode Selection

**Parse argument:**
- Number (e.g., `5`) → Analyze last N commits
- `since-adr` → Since last ADR was created
- `interactive` → Pick from recent commits
- Empty → Ask user which mode

**If no argument provided, use AskUserQuestion:**

```
Question 1:
  header: "Mode"
  question: "Which mode for commit selection?"
  options:
    - label: "Last N commits"
      description: "Analyze a specific number of recent commits"
    - label: "Since last ADR"
      description: "Commits since the last ADR was created"
    - label: "Interactive"
      description: "Pick specific commits from recent history"
  multiSelect: false
```

If "Last N commits" selected, follow up:

```
Question 2:
  header: "Count"
  question: "How many commits to analyze?"
  options:
    - label: "5 commits"
      description: "Quick analysis of recent work"
    - label: "10 commits"
      description: "Standard batch size"
    - label: "20 commits"
      description: "Larger analysis, may spawn subagents"
    - label: "50 commits"
      description: "Comprehensive history, will use subagents"
  multiSelect: false
```

---

## Process

### Step 1: Gather Commits

**Mode: N commits**
```bash
git log -n $N --format="%H|%s|%b" --no-merges
```

**Mode: since-adr**
```bash
# Get last ADR creation time
LAST_ADR=$(ls -t adr/decisions/*.md 2>/dev/null | head -1)
# Get commits since that file was created
git log --since="$(stat -f "%Sm" -t "%Y-%m-%d" "$LAST_ADR" 2>/dev/null || echo "1 week ago")" --format="%H|%s|%b" --no-merges
```

**Mode: interactive**
```bash
# Show recent 20 commits for selection
git log -20 --oneline --no-merges
```

After showing commits, use AskUserQuestion to let user select commit ranges:

```
Question:
  header: "Commits"
  question: "Which commit range do you want to analyze?"
  options:
    - label: "Last 5"
      description: "HEAD~5..HEAD - most recent commits"
    - label: "Last 10"
      description: "HEAD~10..HEAD - recent work"
    - label: "Last week"
      description: "All commits from the past 7 days"
  multiSelect: false
```

User can select "Other" to provide specific commit hashes or ranges.

### Step 2: Count and Route

```bash
# Count commits gathered
COMMIT_COUNT=$(echo "$COMMITS" | wc -l)
```

**Routing decision:**
- `commits <= 10` → Single agent mode (Step 3a)
- `commits > 10` → Subagent mode (Step 3b)

---

### Step 3a: Single Agent Mode (<=10 commits)

Analyze all commits directly:

**For each commit, extract:**
1. **Decision signals** in message:
   - "decided to...", "chose...", "went with..."
   - "instead of...", "rather than..."
   - "because...", "due to..."
2. **Constraints**:
   - "never...", "always...", "must..."
3. **Problem/solution pairs**:
   - What was broken → How it was fixed

**In diffs, look for:**
- New configuration files (architectural choices)
- New patterns (file structure, naming conventions)
- Dependency changes with rationale
- API contract changes

**Skip commits that are:**
- Pure bug fixes with no architectural insight
- Documentation-only changes
- Dependency bumps without rationale
- Formatting/lint changes

**Cluster by topic:**
- Same domain area (auth, API, database, etc.)
- Related problem/solution
- Sequential commits addressing same issue

→ Continue to Step 4

---

### Step 3b: Subagent Mode (>10 commits)

**Batch commits (10 per batch):**
```bash
# Split commits into batches
echo "$COMMITS" | split -l 10
```

**Launch analyzer agents in parallel:**
```
For each batch:
  Use adr-commit-analyzer-agent with batch of commit hashes
```

**Collect compressed findings from all analyzers.**

**Launch clusterer agent:**
```
Use adr-commit-clusterer-agent with all compressed findings
```

→ Continue to Step 4

---

### Step 4: Present Groupings for Approval

**Display proposed ADRs:**

```markdown
## Proposed ADR Groupings

| # | Commits | Proposed ADR Title | Signal |
|---|---------|-------------------|--------|
| 1 | abc123, def456 | API error handling strategy | rationale |
| 2 | ghi789 | Database connection pooling | constraint |

### Excluded (no decision signal)
- jkl012: "Fix typo in README"
- mno345: "Update deps"
```

**Use AskUserQuestion for approval:**

```
Question:
  header: "Action"
  question: "How would you like to proceed with these ADR groupings?"
  options:
    - label: "Approve all"
      description: "Create ADRs as shown above"
    - label: "Merge groups"
      description: "Combine multiple groups into single ADR"
    - label: "Drop some groups"
      description: "Exclude specific groups from ADR creation"
    - label: "Cancel"
      description: "Abort without creating any ADRs"
  multiSelect: false
```

If "Merge groups" or "Drop some groups" selected, present follow-up question with group numbers as options.

**Loop until user selects "Approve all" or "Cancel".**

---

### Step 5: Deduplication Check

Before creating, check for overlap:
```bash
grep -rli "KEYWORDS" adr/decisions/ 2>/dev/null
```

**If overlap found, use AskUserQuestion:**

```
Question:
  header: "Overlap"
  question: "Found potential overlap with existing ADR. How to proceed?"
  options:
    - label: "Create anyway"
      description: "This covers a new perspective worth documenting"
    - label: "Skip this group"
      description: "Existing ADR is sufficient"
    - label: "View existing"
      description: "Show me the existing ADR first"
  multiSelect: false
```

---

### Step 6: Create ADR Files

For each approved group:

```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TITLE=$(echo "$PROPOSED_TITLE" | tr ' ' '-' | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')
```

Write to `adr/decisions/${TIMESTAMP}-${TITLE}.md`:

```markdown
# {YYYYMMDD_HHMMSS}-{short-title}

## Status
Accepted

## Context
{Problem extracted from commits}

**Source commits:**
- {hash}: {subject}

## Decision
{What was chosen and why — extracted from commit messages}

## Consequences

### Positive
{Benefits mentioned or implied}

### Negative
{Trade-offs mentioned or implied}

### Constraints
{Any "never/always/must" statements discovered}
```

---

## Output Summary

```markdown
## 📝 ADRs Created from Commits

**Mode:** {n|since-adr|interactive}
**Commits analyzed:** {count}
**Groups found:** {n}
**ADRs created:** {n}

### Created ADRs

| File | Title | Source Commits |
|------|-------|----------------|
| `20251212_143000-{title}.md` | {Title} | abc1234, def5678 |

### Skipped
- {n} commits had no decision signal
- Group {n} dropped by user

### Next Steps
- Review created ADRs for accuracy
- Run `/adr-review` to check current code against new constraints
```

---

## Error Handling

**No commits found:**
```
No commits found for the specified range.
- If using `n`: try a larger number
- If using `since-adr`: no ADRs exist yet, use `n` mode
- If using `interactive`: ensure branch has commits
```

**No decision signals - use AskUserQuestion:**

```
Question:
  header: "No signals"
  question: "No architectural decisions found. How to proceed?"
  options:
    - label: "Force analysis"
      description: "Create ADRs anyway (may be low-value)"
    - label: "Different commits"
      description: "Select a different commit range"
    - label: "Cancel"
      description: "Exit without creating ADRs"
  multiSelect: false
```

---

## Token Budget

| Phase | Target |
|-------|--------|
| Mode selection | 50 tokens |
| Commit gathering | 100 tokens |
| Analysis display | 400 tokens |
| User interaction | 100 tokens |
| **Total per cycle** | **~650 tokens** |
