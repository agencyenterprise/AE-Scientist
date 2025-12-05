# Next.js Technical Guidance

## Agent
nextjs-expert

## Timestamp
2025-12-04 17:00

## Project Analysis

### Detected Versions
| Package | Version | Notes |
|---------|---------|-------|
| next | 15.4.8 | App Router, Turbopack enabled |
| react | 19.1.2 | React 19 - automatic memoization via React Compiler |
| react-dom | 19.1.2 | Matches React version |
| typescript | ^5 | Modern TypeScript |
| @tanstack/react-query | ^5.90.10 | For server state management |
| zustand | ^5.0.8 | For client state management |
| tailwindcss | ^4 | v4 with @tailwindcss/postcss |

### Router Type
**App Router** - confirmed by:
- `"use client"` directive in target component
- `next dev --turbopack` in dev script
- Modern App Router patterns throughout codebase

### Key Configuration
```typescript
// next.config.ts
const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'http', hostname: 'localhost', port: '8000', pathname: '/conversations/files/**' },
      { protocol: 'https', hostname: '*.railway.app', pathname: '/conversations/files/**' },
    ],
  },
};
```
- No experimental flags required
- Standard App Router configuration

---

## Version-Specific Guidance

### Do's (Next.js 15.4 + React 19)

1. **Use `"use client"` directive only at component entry points**
   - The target component already has `"use client"` correctly placed at line 1
   - No additional files need the directive for this feature

2. **Keep state management local when appropriate**
   - `useState` for filter state is correct (component-scoped, no persistence needed)
   - `useMemo` for derived state (filtered logs) is acceptable but see notes below

3. **Use existing utilities from the codebase**
   - `cn()` from `@/shared/lib/utils` for class merging
   - `getLogLevelColor()` already imported - reuse color patterns

4. **Match established styling patterns**
   - Use `bg-{color}-500/15 text-{color}-400` pattern (seen in `research-utils.tsx`)
   - Dark theme: `bg-slate-800`, `text-slate-400`, `border-slate-700`

### Don'ts (Anti-patterns to Avoid)

1. **Don't over-memoize small computations**
   - For typical log arrays (<1000 items), filtering is fast (<1ms)
   - React 19's compiler may auto-optimize anyway
   - Only add `useMemo` if logs array is large AND filter changes frequently

2. **Don't use dynamic Tailwind classes**
   - **IMPORTANT**: `bg-${color}-500/15` will NOT work - Tailwind requires full class names at build time
   - Use explicit class mappings instead (see code examples below)

3. **Don't add `"use client"` to more files than needed**
   - The filter is entirely within the existing client component
   - No new files need the directive

4. **Don't use inline functions in render for event handlers unnecessarily**
   - For simple `onClick={() => setFilter(value)}`, inline is fine
   - React 19 handles function stability automatically in most cases

---

## React 19 Memoization Guidance

### When to Use useMemo (React 19)

According to React 19 documentation, use `useMemo` when:
- Calculations take **1ms or more** cumulatively
- Passing computed values to `memo()`-wrapped components
- Value is used as a dependency in other hooks

### Recommendation for This Feature

**Option A: With useMemo (Conservative)**
```typescript
const filteredLogs = useMemo(() => {
  if (activeFilter === "all") return logs;
  return logs.filter(log => {
    const level = log.level.toLowerCase();
    if (activeFilter === "warn") {
      return level === "warn" || level === "warning";
    }
    return level === activeFilter;
  });
}, [logs, activeFilter]);
```

**Option B: Without useMemo (React 19 Optimized)**
```typescript
// React 19 Compiler can auto-memoize this
const filteredLogs = activeFilter === "all"
  ? logs
  : logs.filter(log => {
      const level = log.level.toLowerCase();
      if (activeFilter === "warn") {
        return level === "warn" || level === "warning";
      }
      return level === activeFilter;
    });
```

**Verdict**: Use **Option A (with useMemo)** because:
1. Planning phase already specifies `useMemo` - maintain consistency
2. Logs can grow large during long research runs
3. The pattern is explicit and self-documenting
4. React Compiler adoption is not yet universal

---

## Recommended Patterns for This Feature

### Component Structure

The feature is a single-file enhancement. No new files needed.

```
frontend/src/features/research/components/run-detail/
  research-logs-list.tsx   <-- MODIFY THIS FILE ONLY
```

### State Management Pattern

```typescript
"use client";

import { useState, useMemo } from "react";
import { cn } from "@/shared/lib/utils";
// ... existing imports

// Type definition (keep in file - single use)
type LogLevelFilter = "all" | "info" | "warn" | "error";

// Filter button configuration - EXPLICIT classes (Tailwind requirement)
const LOG_FILTER_CONFIG: Record<LogLevelFilter, { label: string; activeClass: string }> = {
  all: {
    label: "all",
    activeClass: "bg-slate-500/15 text-slate-300"
  },
  info: {
    label: "info",
    activeClass: "bg-sky-500/15 text-sky-400"
  },
  warn: {
    label: "warn",
    activeClass: "bg-amber-500/15 text-amber-400"
  },
  error: {
    label: "error",
    activeClass: "bg-red-500/15 text-red-400"
  },
};

const LOG_FILTER_OPTIONS: LogLevelFilter[] = ["all", "info", "warn", "error"];
```

### Event Handler Pattern (React 19)

For simple state updates, inline handlers are fine:

```typescript
// Acceptable - React 19 handles stability
<button onClick={() => setActiveFilter(option)}>
  {LOG_FILTER_CONFIG[option].label}
</button>
```

No need for `useCallback` in this case because:
- The handler is simple (just a state setter)
- Button elements don't benefit from referential equality
- React 19 Compiler optimizes automatically

### Filter UI Pattern

```typescript
<div className="mb-3 flex items-center gap-1">
  {LOG_FILTER_OPTIONS.map(option => (
    <button
      key={option}
      type="button"
      onClick={() => setActiveFilter(option)}
      className={cn(
        "rounded-md px-3 py-1 text-xs font-medium transition-colors",
        activeFilter === option
          ? LOG_FILTER_CONFIG[option].activeClass
          : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
      )}
    >
      {LOG_FILTER_CONFIG[option].label}
    </button>
  ))}
</div>
```

### Accessibility Considerations

Add ARIA attributes for screen reader support:

```typescript
<div className="mb-3 flex items-center gap-1" role="group" aria-label="Filter logs by level">
  {LOG_FILTER_OPTIONS.map(option => (
    <button
      key={option}
      type="button"
      onClick={() => setActiveFilter(option)}
      aria-pressed={activeFilter === option}
      className={cn(/* ... */)}
    >
      {LOG_FILTER_CONFIG[option].label}
    </button>
  ))}
</div>
```

---

## Important: Tailwind Dynamic Class Warning

**Do NOT use template literal classes with Tailwind:**

```typescript
// WRONG - Will NOT work!
className={`bg-${color}-500/15 text-${color}-400`}
```

**Why**: Tailwind scans files at build time and only includes classes it finds as complete strings. Dynamic class names are not detected.

**Correct approach**: Use explicit class mappings as shown in `LOG_FILTER_CONFIG` above.

This is consistent with existing patterns in `research-utils.tsx`:
```typescript
// From getStatusBadge() - uses full class strings
className={`inline-flex items-center rounded-full bg-emerald-500/15 font-medium text-emerald-400`}
```

---

## Code Example: Complete Implementation

```typescript
"use client";

import { useState, useMemo } from "react";
import { Terminal } from "lucide-react";
import { format } from "date-fns";
import type { LogEntry } from "@/types/research";
import { getLogLevelColor } from "../../utils/research-utils";
import { cn } from "@/shared/lib/utils";

// ===== Filter Types and Configuration =====
type LogLevelFilter = "all" | "info" | "warn" | "error";

const LOG_FILTER_CONFIG: Record<LogLevelFilter, { label: string; activeClass: string }> = {
  all: { label: "all", activeClass: "bg-slate-500/15 text-slate-300" },
  info: { label: "info", activeClass: "bg-sky-500/15 text-sky-400" },
  warn: { label: "warn", activeClass: "bg-amber-500/15 text-amber-400" },
  error: { label: "error", activeClass: "bg-red-500/15 text-red-400" },
};

const LOG_FILTER_OPTIONS: LogLevelFilter[] = ["all", "info", "warn", "error"];

interface ResearchLogsListProps {
  logs: LogEntry[];
}

export function ResearchLogsList({ logs }: ResearchLogsListProps) {
  const [activeFilter, setActiveFilter] = useState<LogLevelFilter>("all");

  // Memoize filtered logs - logs array can grow large during research runs
  const filteredLogs = useMemo(() => {
    if (activeFilter === "all") return logs;
    return logs.filter(log => {
      const level = log.level.toLowerCase();
      if (activeFilter === "warn") {
        return level === "warn" || level === "warning";
      }
      return level === activeFilter;
    });
  }, [logs, activeFilter]);

  if (logs.length === 0) {
    return null;
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-800 bg-slate-900/50 p-6">
      {/* Header */}
      <div className="mb-4 flex items-center gap-2">
        <Terminal className="h-5 w-5 text-slate-400" />
        <h2 className="text-lg font-semibold text-white">Logs</h2>
        <span className="text-sm text-slate-400">
          ({filteredLogs.length}{activeFilter !== "all" ? `/${logs.length}` : ""})
        </span>
      </div>

      {/* Filter Buttons */}
      <div className="mb-3 flex items-center gap-1" role="group" aria-label="Filter logs by level">
        {LOG_FILTER_OPTIONS.map(option => (
          <button
            key={option}
            type="button"
            onClick={() => setActiveFilter(option)}
            aria-pressed={activeFilter === option}
            className={cn(
              "rounded-md px-3 py-1 text-xs font-medium transition-colors",
              activeFilter === option
                ? LOG_FILTER_CONFIG[option].activeClass
                : "text-slate-500 hover:text-slate-300 hover:bg-slate-800"
            )}
          >
            {LOG_FILTER_CONFIG[option].label}
          </button>
        ))}
      </div>

      {/* Log List */}
      <div className="min-h-0 flex-1 overflow-y-auto rounded-lg bg-slate-950 p-4 font-mono text-sm">
        {filteredLogs.map(log => (
          <div key={log.id} className="flex gap-3 py-1">
            <span className="flex-shrink-0 text-slate-600">
              {format(new Date(log.created_at), "HH:mm:ss")}
            </span>
            <span
              className={`flex-shrink-0 uppercase ${getLogLevelColor(log.level)}`}
              style={{ width: "50px" }}
            >
              {log.level}
            </span>
            <span className="text-slate-300">{log.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## Documentation References

- [useMemo - React](https://react.dev/reference/react/useMemo)
- [Directives: use client - Next.js](https://nextjs.org/docs/app/api-reference/directives/use-client)
- [Client Components - Next.js](https://nextjs.org/docs/app/building-your-application/rendering/client-components)
- [React 19 Memoization Guide](https://dev.to/joodi/react-19-memoization-is-usememo-usecallback-no-longer-necessary-3ifn)

---

## For Executor

### Key Points to Follow

1. **Add one import**: `import { cn } from "@/shared/lib/utils"`
   - Also add `useState, useMemo` to the React imports

2. **Use explicit Tailwind class mappings** - Do NOT use template literals for class names

3. **Place filter UI between header and log list** - After the title row, before the scrollable log container

4. **Use `useMemo` for filtered logs** - Consistent with planning docs and safe for potentially large log arrays

5. **Handle "warn" vs "warning" case** - The codebase has both (see `LOG_LEVEL_COLORS` in research-utils.tsx)

6. **Maintain dark theme styling** - Use existing color patterns from the component

### Imports Needed

```typescript
import { useState, useMemo } from "react";  // Add to existing or new
import { cn } from "@/shared/lib/utils";     // New import
```

### Testing Checklist

- [ ] "all" filter shows all logs
- [ ] "info" filter shows only INFO level logs
- [ ] "warn" filter shows both WARN and WARNING level logs
- [ ] "error" filter shows only ERROR level logs
- [ ] Log count updates correctly (filtered/total format)
- [ ] Active button has colored background
- [ ] Inactive buttons have hover state
- [ ] Keyboard navigation works (Tab between buttons)

---

## Summary

| Aspect | Recommendation |
|--------|----------------|
| State management | `useState` for filter (local scope) |
| Derived state | `useMemo` for filtered logs (safe default) |
| Event handlers | Inline functions (React 19 optimized) |
| Tailwind classes | Explicit strings in config object |
| Accessibility | `role="group"`, `aria-label`, `aria-pressed` |
| New files | None - single file modification |
| New dependencies | None - uses existing utilities |
