# Architecture Decision Records

This folder contains Architecture Decision Records (ADRs) — append-only documents that capture significant technical decisions.

## Why ADRs?

- **Historical context** — Understand why decisions were made
- **Onboarding** — New team members learn the "why" behind architecture
- **Prevent re-litigation** — Avoid revisiting settled decisions

## Format

```markdown
# {YYYYMMDD_HHMMSS}-{short-title}

## Status
Proposed | Accepted | Deprecated | Superseded by {ADR}

## Context
{What is the issue? What forces are at play?}

## Decision
{What did we decide to do?}

## Consequences
{What are the results? Both positive and negative.}
```

## Rules

1. **Append-only** — Never edit past ADRs, only add new ones
2. **Supersede, don't delete** — Mark old ADR as superseded, add new one
3. **Keep brief** — Focus on decision and rationale, not implementation
4. **Timestamp prefix** — Use YYYYMMDD_HHMMSS for precise chronological ordering

## Usage

Before proposing architectural changes:
```bash
ls adr/decisions/
```

Check if the topic has been decided before.

## Creating ADRs

When making significant decisions:

```bash
touch adr/decisions/$(date +%Y%m%d_%H%M%S)-{short-title}.md
```

Or ask Claude:
> "Create an ADR for {decision}"
