---
description: Explore this codebase efficiently with structured search
tools: Read, Glob, Grep, Bash(grep:*), Bash(find:*), Bash(cat:*), Bash(head:*)
---

# ADR Research Codebase Skill

## When to Use

- Understanding existing code before changes
- Tracing data flows
- Finding where functionality lives
- Discovering patterns and conventions

## Search Areas

### Frontend (Next.js)

| Area       | Path                     | Contains                                   |
| ---------- | ------------------------ | ------------------------------------------ |
| Features   | `frontend/src/features/` | Feature modules (components, hooks, utils) |
| Shared     | `frontend/src/shared/`   | Shared components, lib, providers          |
| App Routes | `frontend/src/app/`      | Next.js App Router pages                   |
| Types      | `frontend/src/types/`    | TypeScript types (api.gen.ts)              |

### Backend (FastAPI)

| Area       | Path                            | Contains                         |
| ---------- | ------------------------------- | -------------------------------- |
| API Routes | `server/app/api/`               | FastAPI endpoint routers         |
| Models     | `server/app/models/`            | Pydantic request/response models |
| Services   | `server/app/services/`          | Business logic services          |
| Database   | `server/app/services/database/` | DB query functions               |

### Research Pipeline

| Area         | Path                                         | Contains            |
| ------------ | -------------------------------------------- | ------------------- |
| AI Scientist | `research_pipeline/ai_scientist/`            | Core ML pipeline    |
| Tree Search  | `research_pipeline/ai_scientist/treesearch/` | Research tree logic |
| Ideation     | `research_pipeline/ai_scientist/ideation/`   | Idea generation     |

### Orchestrator

| Area       | Path                       | Contains          |
| ---------- | -------------------------- | ----------------- |
| Components | `orchestrator/components/` | UI components     |
| Lib        | `orchestrator/lib/`        | Utility functions |

## Process

### Step 1: Keyword Search

```bash
# Find topic in code
grep -rn "TOPIC" src/ --include="*.ts" --include="*.tsx" | head -30
```

### Step 2: File Discovery

```bash
# Find files by name
find . -type f -name "*TOPIC*" -not -path "*/node_modules/*" | head -10
```

### Step 3: Import Tracing

```bash
# Trace imports/exports
grep -rn "export.*TOPIC\|import.*TOPIC" src/ | head -20
```

### Step 4: Deep Dive

For each key file:

1. Read specific section (not whole file)
2. Note exact line numbers
3. Trace to integration points

## Output Requirements

Every finding must include:

- File path
- Line numbers
- Action classification (modify/reference)

See `patterns.md` for codebase-specific patterns.

## Anti-Patterns

- ❌ Reading entire files
- ❌ Prose descriptions without line refs
- ✅ File:line precision
- ✅ Dense, compressed output
