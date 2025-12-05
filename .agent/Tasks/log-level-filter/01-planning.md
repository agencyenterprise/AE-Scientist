# Planning Phase

## Agent
feature-planner

## Timestamp
2025-12-04 16:00

## Input Received
- Context: `.agent/Tasks/log-level-filter/00-context.md`
- Project docs consulted:
    - `.agent/README.md`
    - `.agent/System/frontend_architecture.md`
    - `.agent/SOP/frontend_features.md`
    - `frontend/src/features/research/components/run-detail/research-logs-list.tsx` (target component)
    - `frontend/src/features/research/utils/research-utils.tsx` (existing utilities)
    - `frontend/src/types/research.ts` (LogEntry type)
    - `frontend/src/shared/components/ui/button.tsx` (button styling reference)
    - `frontend/src/features/dashboard/components/DashboardFilterSortBar.tsx` (filter pattern reference)

## Reasoning

### Why This Approach

1. **Single Component Modification vs New Component**:
   - Chose to modify existing `research-logs-list.tsx` rather than create separate filter component
   - Filter state is tightly coupled to the logs display
   - No reuse scenario for this filter elsewhere in the codebase
   - Keeps implementation simple and localized

2. **Local State vs Context/External State**:
   - Chose `useState` hook for filter state
   - Filter preference doesn't need to persist across navigation
   - No other components need to know the filter state
   - Follows frontend_architecture.md Section 5: "Use React's useState for simple, component-scoped state"

3. **useMemo for Filtered Logs**:
   - Chose `useMemo` to derive filtered logs from props
   - Avoids unnecessary re-filtering on every render
   - Dependencies: `logs` array and `activeFilter` state

4. **Button Styling Approach**:
   - Chose inline Tailwind classes over shadcn Button component
   - Matches existing styling in the component (dark theme, slate backgrounds)
   - Filter buttons are tightly integrated, not standalone actions
   - Using `cn()` utility for conditional class merging

5. **Color Mapping Strategy**:
   - Reuse existing color scheme from `LOG_LEVEL_COLORS` in research-utils.tsx
   - info: sky-400 (blue)
   - warn/warning: amber-400 (yellow/orange)
   - error: red-400 (red)
   - all: slate-400 (neutral)

### Pattern Selection
- Chose pattern: **Component-local state with useMemo derivation**
- Because: Simple UI state that doesn't need external access
- Reference: Similar to how `useConversationsFilter.ts` filters data, but simpler inline version

### Dependencies Identified
- **LogEntry type**: Already imported from `@/types/research`
- **getLogLevelColor**: Already imported from `../../utils/research-utils`
- **cn utility**: Will need to import from `@/shared/lib/utils`
- **useState, useMemo**: React hooks (already using React in component)

### Risks & Considerations
- **Risk 1**: Log levels may have unexpected values (DEBUG, TRACE, etc.)
  - Mitigation: "all" filter shows everything; specific filters only match exact levels
  - Non-matching levels will only appear when "all" is selected
- **Risk 2**: Performance with large log arrays
  - Mitigation: useMemo ensures filtering only runs when logs or filter changes
  - Current usage shows logs streamed incrementally, not bulk loaded
- **Risk 3**: Visual consistency with rest of component
  - Mitigation: Using same color palette and dark theme styling as existing log display

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| State location | Local useState in component | Filter state doesn't need to persist or be shared |
| Filtering method | useMemo with array filter | Performance optimization, clean derivation pattern |
| Button styling | Custom Tailwind classes | Matches existing component styling, dark theme |
| Filter types | "all", "info", "warn", "error" | Covers common log levels; "warn" matches both "warn" and "warning" |
| Button placement | After header, before log list | Natural position for filter controls |
| Log count display | Show filtered/total | Gives user context of filter effect |

## Output Summary
- PRD created: `.agent/Tasks/log-level-filter/PRD.md`
- Files to create: 0 (enhancement only)
- Files to modify: 1 (`research-logs-list.tsx`)
- Estimated complexity: **Simple** - Single component, ~30-40 lines added

## Implementation Outline

### Changes to research-logs-list.tsx

1. **New imports**:
   ```typescript
   import { useState, useMemo } from "react";
   import { cn } from "@/shared/lib/utils";
   ```

2. **New type and constants**:
   ```typescript
   type LogLevelFilter = "all" | "info" | "warn" | "error";

   const LOG_FILTER_OPTIONS: { value: LogLevelFilter; label: string; color: string }[] = [
     { value: "all", label: "all", color: "slate" },
     { value: "info", label: "info", color: "sky" },
     { value: "warn", label: "warn", color: "amber" },
     { value: "error", label: "error", color: "red" },
   ];
   ```

3. **State and filtering**:
   ```typescript
   const [activeFilter, setActiveFilter] = useState<LogLevelFilter>("all");

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

4. **Filter UI (between header and log list)**:
   ```typescript
   <div className="mb-3 flex items-center gap-1">
     {LOG_FILTER_OPTIONS.map(option => (
       <button
         key={option.value}
         onClick={() => setActiveFilter(option.value)}
         className={cn(
           "rounded-md px-3 py-1 text-xs font-medium transition-colors",
           activeFilter === option.value
             ? `bg-${option.color}-500/20 text-${option.color}-400`
             : "text-slate-500 hover:text-slate-300"
         )}
       >
         {option.label}
       </button>
     ))}
   </div>
   ```

5. **Update log count in header**:
   ```typescript
   <span className="text-sm text-slate-400">
     ({filteredLogs.length}{activeFilter !== "all" ? `/${logs.length}` : ""})
   </span>
   ```

6. **Use filteredLogs in render**:
   ```typescript
   {filteredLogs.map(log => (
     // existing log entry rendering
   ))}
   ```

## For Next Phase (Architecture)

Key considerations for the architect:
1. **No architectural changes needed** - This is a simple component enhancement
2. **No new dependencies** - Uses existing utilities and React hooks
3. **No API changes** - Purely client-side filtering
4. **Could skip Architecture phase** - Implementation is straightforward

## Approval Status
- [ ] Pending approval
- [ ] Approved - proceed to Architecture (or skip to Implementation)
- [ ] Modified - see feedback below

### Feedback (if modified)
{User feedback will be added here}
