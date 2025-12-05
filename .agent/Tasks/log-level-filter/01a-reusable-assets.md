# Reusable Assets Inventory

## Agent
codebase-analyzer

## Timestamp
2025-12-04 16:30

## Feature Requirements Summary
Add a log level filter UI to `research-logs-list.tsx` with horizontal buttons (ALL, INFO, WARN, ERROR) that filter displayed logs by severity level. Uses local component state with `useState` and `useMemo` for client-side filtering.

---

## MUST REUSE (Exact Match Found)

These assets already exist and MUST be used instead of creating new ones:

### Frontend

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| Class merging utility | `cn()` | `frontend/src/shared/lib/utils.ts` | `import { cn } from "@/shared/lib/utils"` |
| Log level colors | `LOG_LEVEL_COLORS` (internal) | `frontend/src/features/research/utils/research-utils.tsx` | N/A - colors defined there for reference |
| Log level color getter | `getLogLevelColor()` | `frontend/src/features/research/utils/research-utils.tsx` | `import { getLogLevelColor } from "../../utils/research-utils"` (already imported) |
| LogEntry type | `LogEntry` | `frontend/src/types/research.ts` | `import type { LogEntry } from "@/types/research"` (already imported) |
| Filter button CSS | `.btn-filter`, `.btn-filter-active`, `.btn-filter-inactive` | `frontend/src/app/globals.css` | Classes available globally |

### Color Mapping from Existing Code

The codebase already defines these log level colors in `research-utils.tsx`:
```typescript
const LOG_LEVEL_COLORS: Record<string, string> = {
  error: "text-red-400",
  warn: "text-amber-400",
  warning: "text-amber-400",
  info: "text-sky-400",
  debug: "text-slate-400",
};
```

Filter buttons should use matching background variants:
- `error`: `bg-red-500/15 text-red-400`
- `warn`: `bg-amber-500/15 text-amber-400`
- `info`: `bg-sky-500/15 text-sky-400`
- `all`: `bg-slate-500/15 text-slate-400` (neutral)

---

## CONSIDER REUSING (Similar Found)

These assets are similar and might be adaptable:

### Frontend

| Need | Similar Asset | Location | Notes |
|------|---------------|----------|-------|
| Toggle button styling | Navigation tabs in Header | `frontend/src/shared/components/Header.tsx` | Uses `bg-{color}-500/15 text-{color}-400` pattern for active state, matching our needs |
| Filter button pattern | DashboardFilterSortBar | `frontend/src/features/dashboard/components/DashboardFilterSortBar.tsx` | Uses `btn-secondary` class, select-based filtering |
| Filtering hook pattern | `useConversationsFilter` | `frontend/src/features/conversation/hooks/useConversationsFilter.ts` | Uses `useState` + `useMemo` pattern; can adapt for simpler inline version |
| Pill badge styling | Live/Reconnect badges | `frontend/src/features/research/components/run-detail/research-run-header.tsx` | `rounded-full bg-{color}-500/15 px-3 py-1 text-xs font-medium text-{color}-400` pattern |
| Status badge pattern | `getStatusBadge()` | `frontend/src/features/research/utils/research-utils.tsx` | Shows pattern for styled badges with color variants |

### CSS Classes Available (globals.css)

```css
/* Filter button base - AVAILABLE */
.btn-filter {
  @apply px-2 py-1 text-xs rounded border transition;
}

.btn-filter-inactive {
  @apply bg-muted text-foreground/80 border-border hover:bg-secondary;
}

.btn-filter-active {
  @apply bg-foreground text-background border-foreground;
}
```

**Note**: The existing `.btn-filter-*` classes use a simple dark/light toggle approach. For color-coded log level filters, we should use custom Tailwind classes matching the `bg-{color}-500/15 text-{color}-400` pattern used elsewhere in the research feature.

---

## CREATE NEW (Nothing Found)

These need to be created as no existing solution was found:

| Need | Suggested Location | Notes |
|------|-------------------|-------|
| `LogLevelFilter` type | Inline in `research-logs-list.tsx` | `type LogLevelFilter = "all" \| "info" \| "warn" \| "error"` |
| `LOG_FILTER_OPTIONS` constant | Inline in `research-logs-list.tsx` | Array of filter options with value, label, color |
| Filter state + useMemo logic | Inline in `research-logs-list.tsx` | Simple enough to keep in component |

**No new files or shared utilities needed** - this is a simple, localized enhancement.

---

## CONSIDER EXTRACTING TO SHARED

Currently not applicable. The log level filter is specific to the research logs list and doesn't have immediate reuse scenarios.

**Future consideration**: If we add log filtering to other features, consider extracting:
- A `LogLevelFilterButtons` component to `frontend/src/features/research/components/common/`
- A `useLogFilter` hook to `frontend/src/features/research/hooks/`

---

## Patterns Already Established

### State Management Pattern
- Use React `useState` for local component state (per `frontend_architecture.md`)
- Use `useMemo` for derived/computed values
- See: `useConversationsFilter.ts` for pattern reference

### Button/Badge Styling Pattern
The codebase uses consistent color styling:
```tsx
// Active/highlighted state pattern
className="bg-{color}-500/15 text-{color}-400"

// With border variant
className="rounded-full bg-{color}-500/15 px-3 py-1 text-xs font-medium text-{color}-400"
```

Color palette mapping:
| Semantic | Color | Example |
|----------|-------|---------|
| Info/Primary | sky | `bg-sky-500/15 text-sky-400` |
| Warning | amber | `bg-amber-500/15 text-amber-400` |
| Error/Danger | red | `bg-red-500/15 text-red-400` |
| Neutral/Default | slate | `bg-slate-500/15 text-slate-400` |
| Success | emerald | `bg-emerald-500/15 text-emerald-400` |

### Filter Logic Pattern
From `useConversationsFilter.ts`:
```typescript
const filteredItems = useMemo(() => {
  if (noFilter) return items;
  return items.filter(item => /* condition */);
}, [items, filterValue]);
```

### Dark Theme Context
The research detail page uses dark theme styling:
- Background: `bg-slate-900/50`, `bg-slate-950`
- Borders: `border-slate-800`, `border-slate-700`
- Text: `text-slate-300`, `text-slate-400`, `text-white`
- Inactive states: `text-slate-500 hover:text-slate-300`

---

## For Architect

Key reusability requirements:
1. **DO NOT** create new utility file - use existing `cn()` and `getLogLevelColor()`
2. **REUSE** color scheme from existing `LOG_LEVEL_COLORS` mapping
3. **FOLLOW** patterns from `Header.tsx` and `research-run-header.tsx` for active/inactive styling
4. **MATCH** dark theme styling used in `research-logs-list.tsx`

Architecture phase can be **SKIPPED** - this is a simple component enhancement with:
- No new files
- No new dependencies  
- No API changes
- Single file modification

## For Executor

Before implementing:
1. The `cn()` utility is already available at `@/shared/lib/utils`
2. `getLogLevelColor()` is already imported in the target component
3. Use `bg-{color}-500/15 text-{color}-400` pattern for active buttons
4. Use `text-slate-500 hover:text-slate-300` for inactive buttons
5. Keep all new code inline in `research-logs-list.tsx`

Implementation should add approximately 30-40 lines to the existing component.
