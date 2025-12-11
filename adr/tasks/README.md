# Tasks

Temporary workspace for in-progress work. Contents are disposable after merge.

## Structure

```
adr/tasks/
└── YYYYMMDD_HHMMSS-{task-name}/
    ├── research.md   # Research agent output
    ├── plan.md       # Planner agent output
    └── progress.md   # Compactor output (if needed)
```

## Lifecycle

1. **Create** — When starting `/feature {description}`
2. **Use** — During research, planning, execution
3. **Delete** — After PR merged

## Naming

Use timestamp prefix with descriptive task names:
- `20251211_143022-add-notifications`
- `20251211_151545-fix-auth-refresh`
- `20251212_092130-refactor-user-service`

Format: `YYYYMMDD_HHMMSS-{descriptive-name}`

## Git

Consider adding to `.gitignore`:
```
adr/tasks/
```

Or commit for team visibility:
```
adr/tasks/*.md
```

## Cleanup

After merge:
```bash
rm -rf adr/tasks/20251211_143022-add-notifications
```

Or prune all:
```bash
rm -rf adr/tasks/*
```
