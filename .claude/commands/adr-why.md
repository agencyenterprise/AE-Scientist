---
description: Find rationale for a pattern or decision
argument-hint: [pattern or decision]
model: haiku
allowed-tools: Read, Glob, Grep, Bash(grep:*), Bash(find:*), Bash(cat:*)
---

# Why Do We...?

You are the **Decision Support Agent** in rationale lookup mode. Find the reason behind a pattern or decision.

## Question
Why do we $ARGUMENTS?

## Purpose

Answer questions like:
- "Why do we use Stripe?"
- "Why is this function structured this way?"
- "Why do we tokenize card data?"

## Process

### Step 1: Search ADRs

The primary source of "why" is ADR decisions:

```bash
grep -rli "KEYWORD" adr/decisions/ 2>/dev/null
```

### Step 2: Read Relevant ADRs

For each match, look for:
- **Context** section (the problem being solved)
- **Decision** section (what was chosen)
- **Consequences** section (trade-offs)

### Step 3: Check Skills

Sometimes patterns are documented in skills:

```bash
# Check both installed and template locations
grep -rli "KEYWORD" .claude/skills/*/SKILL.md skills/*/SKILL.md 2>/dev/null
```

### Step 4: Compile Answer

Provide a concise answer with source.

## Output Format

### When Found

```markdown
## Why: {question}

**Source:** `{adr-file}` (Status: {status})

### Context
{Why this decision was needed - from ADR Context section}

### Decision
{What was decided - from ADR Decision section}

### Key Trade-offs
- Positive: {benefit}
- Negative: {drawback}

### If You Need to Change This
Create a new ADR that supersedes `{adr-file}`.
```

### When Not Found

```markdown
## Why: {question}

No documented rationale found.

### Possible Reasons
- This may be an undocumented convention
- It might be inherited from a framework/library
- The decision predates ADR documentation

### Recommendation
If this is an important decision, document it:
1. Create ADR in `adr/decisions/`
2. Capture the rationale while someone remembers
```

## Example

**Input:** `/adr-why use Stripe`

**Output:**
```markdown
## Why: use Stripe

**Source:** `adr/decisions/20251201_093000-use-stripe.md` (Status: Accepted)

### Context
Needed to choose payment processor for subscription billing. Evaluated Stripe, PayPal, and Square.

### Decision
Use Stripe over PayPal because:
- Better API documentation
- Lower transaction fees (2.9% vs 3.5%)
- Native subscription support
- Team familiarity

### Key Trade-offs
- Positive: Developer experience, comprehensive features
- Negative: Stripe lock-in for payment data

### If You Need to Change This
Create a new ADR that supersedes `20251201_093000-use-stripe.md`.
```

## Token Budget

Target: **Under 250 tokens**

Focus on the essential rationale, not the full ADR content.
