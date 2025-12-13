---
name: adr-research-codebase
description: Explore AE-Scientist codebase efficiently with structured search across TypeScript, Python, and MDX
allowed-tools: Read, Glob, Grep, Bash(grep:*), Bash(find:*), Bash(cat:*), Bash(head:*)
---

# ADR Research Codebase Skill

## When to Use

- Understanding existing code before changes
- Tracing data flows
- Finding where functionality lives
- Discovering patterns and conventions

## Search Areas

| Area              | Path                              | Contains                                     |
| ----------------- | --------------------------------- | -------------------------------------------- |
| Frontend Features | `frontend/src/features/`          | Feature modules (research, conversation)     |
| Shared Frontend   | `frontend/src/shared/`            | Hooks, lib, components, providers            |
| Frontend Types    | `frontend/src/types/`             | TypeScript type definitions                  |
| Server API        | `server/app/api/`                 | FastAPI route handlers                       |
| Server Services   | `server/app/services/`            | Business logic (database, scraper, pipeline) |
| Server Models     | `server/app/models/`              | Pydantic models                              |
| Orchestrator API  | `orchestrator/app/api/`           | Next.js API routes                           |
| Orchestrator Lib  | `orchestrator/lib/`               | Repos, services, schemas, state              |
| Research Pipeline | `research_pipeline/ai_scientist/` | ML pipeline (treesearch, llm, telemetry)     |
| ADR System        | `.claude/`, `adr/`                | Agents, commands, skills, decisions          |

## Process

### Step 1: Keyword Search

```bash
# Multi-language search (TypeScript, Python, MDX)
grep -rn "TOPIC" frontend/src/ orchestrator/ --include="*.ts" --include="*.tsx" | head -20
grep -rn "TOPIC" server/ research_pipeline/ --include="*.py" | head -20
grep -rn "TOPIC" .claude/ adr/ --include="*.md" | head -10
```

### Step 2: File Discovery

```bash
# Find files by name
find . -type f -name "*TOPIC*" \
  -not -path "*/node_modules/*" \
  -not -path "*/.next/*" \
  -not -path "*/venv/*" \
  -not -path "*/__pycache__/*" | head -15
```

### Step 3: Import Tracing

```bash
# Trace imports/exports (TypeScript)
grep -rn "export.*TOPIC\|import.*TOPIC" frontend/ orchestrator/ | head -15
# Trace imports (Python)
grep -rn "from.*TOPIC\|import.*TOPIC" server/ research_pipeline/ | head -15
```

### Step 4: Data Flow Tracing

```bash
# For feature research: trace data flow across boundaries
# Frontend → API client
grep -rn "apiFetch\|api\." frontend/src/features/TOPIC/
# API routes → Services
grep -rn "router\.\(get\|post\)" server/app/api/TOPIC* orchestrator/app/api/TOPIC*/
# Services → Database
grep -rn "collection\|query" orchestrator/lib/repos/ server/app/services/database/
```

### Step 5: ADR Context Check

```bash
# Check for related ADRs and constraints
grep -rn "TOPIC" adr/decisions/ | head -10
grep -rn "TOPIC" .claude/agents/ .claude/skills/ | head -10
```

### Step 6: Deep Dive

For each key file:

1. Read specific section (not whole file)
2. Note exact line numbers
3. Trace to integration points
4. Document layer (frontend/server/orchestrator/pipeline)

## Output Requirements

Use structured templates based on research type:

**Feature Research:**

```markdown
## Feature: {name}

### Frontend

- Component: `path/to/Component.tsx:line`
- Hook: `path/to/useHook.ts:line`
- Type: `path/to/type.ts:line`

### Backend

- API: `path/to/route.{py|ts}:line`
- Service: `path/to/service.{py|ts}:line`
- Model: `path/to/model.{py|ts}:line`

### Data Flow

{Frontend} → {API} → {Service} → {Database/External}

### Constraints

- ADR: `adr/decisions/{adr-file}.md`
- Pattern: `{pattern description}`
```

**Bug Research:**

```markdown
## Bug: {description}

### Reproduction Path

- Entry: `path/to/file:line`
- Error site: `path/to/file:line`
- Root cause: `path/to/file:line`

### Related Code

- `path/to/file:line` - {what/why}

### Fix Strategy

{brief description}
```

**Pattern Research:**

```markdown
## Pattern: {name}

### Instances

| File        | Lines   | Usage     |
| ----------- | ------- | --------- |
| `path:line` | {range} | {context} |

### Rationale

- ADR: `adr/decisions/{adr}.md` (if exists)
- Convention: {description}
```

Every finding must include:

- File path
- Line numbers
- Action classification (modify/reference)
- Layer classification (frontend/server/orchestrator/pipeline/adr)

See `patterns.md` for codebase-specific patterns.

## Anti-Patterns

- ❌ Reading entire files
- ❌ Prose descriptions without line refs
- ❌ Ignoring ADR decisions and constraints
- ❌ Searching only one language in polyglot codebase
- ❌ Missing data flow across service boundaries
- ✅ File:line precision
- ✅ Dense, compressed output
- ✅ Check ADRs before proposing changes
- ✅ Trace data flows across all layers
