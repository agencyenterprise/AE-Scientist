# ADR (Architecture & Development Records)

This folder contains documentation that persists across development cycles.

## Structure

```
adr/
├── decisions/      # Architecture Decision Records (permanent)
│   └── YYYYMMDD_HHMMSS-*.md
└── tasks/          # Active work (disposable after merge)
    └── YYYYMMDD_HHMMSS-{task-name}/
        ├── research.md
        ├── plan.md
        └── progress.md
```

## Subfolders

### `decisions/`
**Permanent** — Architecture Decision Records capturing significant technical decisions.
- Append-only (never edit, only supersede)
- Check before proposing architectural changes
- See `decisions/README.md` for format

### `tasks/`
**Temporary** — Workspace for in-progress features.
- Created by `/feature` command
- Contains research, plans, and progress files
- Delete after PR merged
- See `tasks/README.md` for lifecycle

## Philosophy

> Skills teach HOW. Decisions capture WHY. Tasks track WHAT.

- **Skills** (`.claude/skills/`) — Procedural expertise, loaded on-demand
- **Decisions** (`adr/decisions/`) — Architectural rationale, permanent record
- **Tasks** (`adr/tasks/`) — Active work, disposable
