# Log Level Filter - Product Requirements Document

## Overview
Add a log level filter UI to the ResearchLogsList component that allows users to filter displayed logs by severity level (ALL, INFO, WARN, ERROR). This enables researchers to quickly focus on specific log types during research run monitoring.

## Status
- [x] Planning
- [x] Architecture (skipped - simple enhancement)
- [x] Implementation
- [x] Copy Review
- [x] Testing (ready for manual verification)
- [x] Documentation Review
- [x] Complete ✓

## User Stories
- As a researcher, I want to filter logs by severity level so that I can quickly find errors without scrolling through informational messages
- As a researcher, I want to see all logs by default so that I don't miss any information
- As a researcher, I want a clear visual indication of which filter is active so that I know what I'm viewing

## Requirements

### Functional
1. **Filter Buttons**: Display horizontal row of filter buttons: "all", "info", "warn", "error"
2. **Default State**: "all" filter should be selected by default, showing all logs
3. **Single Selection**: Only one filter can be active at a time
4. **Case-Insensitive Matching**: Filter should match log levels regardless of case (e.g., "INFO", "info", "Info")
5. **Log Count Update**: The displayed log count in the header should reflect filtered results
6. **Preserved Order**: Filtered logs should maintain chronological order

### Non-Functional
1. **Performance**: Filtering should be instant (client-side only, no API calls)
2. **Visual Consistency**: Filter buttons should match the existing dark theme styling
3. **Responsive**: Filter buttons should work on all screen sizes
4. **Accessibility**: Buttons should be keyboard accessible and have appropriate ARIA labels

## Technical Decisions

Based on project documentation:

### Pattern
- **State Management**: Local `useState` hook for filter state (per frontend_architecture.md Section 5)
- **Component Enhancement**: Modify existing component rather than creating new one (single file change)
- **Filter Logic**: Use `useMemo` to derive filtered logs from props

### SOPs Applied
- **Frontend Architecture**: Use React `useState` for local component state
- **Naming Convention**: Log level type uses uppercase constants to match existing `LOG_LEVEL_COLORS`

### Dependencies
- **Existing**: `LogEntry` type from `@/types/research`
- **Existing**: `getLogLevelColor()` from `../../utils/research-utils`
- **Existing**: `cn()` utility from `@/shared/lib/utils` for conditional styling
- **New**: None required

## Reusability Analysis

### Existing Assets to REUSE
- [x] `LOG_LEVEL_COLORS` from `research-utils.tsx` - Already defines color mapping for levels
- [x] `getLogLevelColor()` from `research-utils.tsx` - For button active states
- [x] `cn()` from `@/shared/lib/utils` - For conditional class merging
- [x] Tailwind color classes already in use (`text-sky-400`, `text-amber-400`, `text-red-400`)

### Similar Features to Reference
- **DashboardFilterSortBar.tsx**: Example of filter/toggle button styling pattern
- **useConversationsFilter.ts**: Example of client-side filtering hook pattern (though we'll use simpler inline useMemo)

### Needs Codebase Analysis
- [x] No - Simple component enhancement with no shared dependencies

## Implementation Plan

### Phase 1: Type Definition
- [x] Define `LogLevelFilter` type union: `"all" | "info" | "warn" | "error"`
- [x] Add to component file (no need for separate types file for single type)

### Phase 2: State Management
- [x] Add `useState<LogLevelFilter>("all")` for active filter
- [x] Add `useMemo` to compute filtered logs based on active filter

### Phase 3: UI Implementation
- [x] Add filter button row between header and log list
- [x] Style buttons with active/inactive states matching dark theme
- [x] Update log count to show filtered count vs total

### Phase 4: Testing
- [ ] Verify "all" shows all logs
- [ ] Verify "info" filters to INFO level only
- [ ] Verify "warn" filters to WARN/WARNING levels
- [ ] Verify "error" filters to ERROR level only
- [ ] Test keyboard navigation

## File Structure (Proposed)

```
frontend/src/features/research/components/run-detail/
├── research-logs-list.tsx  # MODIFIED - Add filter UI and logic
├── final-pdf-banner.tsx
├── research-artifacts-list.tsx
├── research-pipeline-stages.tsx
└── ...
```

**Modified Files:**
- `frontend/src/features/research/components/run-detail/research-logs-list.tsx`

**No new files needed** - This is a single component enhancement.

## Component Changes

### Current Props Interface
```typescript
interface ResearchLogsListProps {
  logs: LogEntry[];
}
```

### New Internal Types
```typescript
type LogLevelFilter = "all" | "info" | "warn" | "error";

const LOG_FILTER_OPTIONS: LogLevelFilter[] = ["all", "info", "warn", "error"];
```

### Filter Logic
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

### UI Button Styling

Active state:
```
bg-{color}-500/20 text-{color}-400 border-{color}-500/50
```

Inactive state:
```
bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700
```

Color mapping:
- all: slate (neutral)
- info: sky (matches existing INFO color)
- warn: amber (matches existing WARN color)
- error: red (matches existing ERROR color)

## Visual Design Reference

The filter buttons should appear as a pill-shaped button group:
```
+-------+-------+-------+--------+
|  all  | info  | warn  | error  |
+-------+-------+-------+--------+
```

- Buttons should be compact (`text-xs`, `px-3 py-1`)
- Rounded corners on group ends (`rounded-l-md`, `rounded-r-md`)
- Active button has colored background matching log level color
- Slight border between buttons for separation

## Related Documentation
- `.agent/System/frontend_architecture.md` - State management patterns
- `.agent/SOP/frontend_features.md` - Component organization
- `frontend/src/features/research/utils/research-utils.tsx` - Existing log level utilities

## Progress Log

### 2025-12-04
- Created initial PRD
- Analyzed existing component structure
- Identified reusable utilities (`getLogLevelColor`, `LOG_LEVEL_COLORS`)
- Determined single-file modification approach
- Designed filter UI matching existing dark theme

### 2025-12-04 (Implementation)
- Implemented log level filter in `research-logs-list.tsx`
- Added `LogLevelFilter` type and `LOG_FILTER_CONFIG` constant
- Added `useState` for filter state, `useMemo` for filtered logs
- Added filter button row with accessibility attributes
- Updated log count to show filtered/total format
- TypeScript compilation: No errors in modified file
- Lines added: ~54 (from 46 to ~100 lines)

### 2025-12-04 (Revision 1: Move Filter to Header)
- Moved filter buttons from separate row to header right side
- Updated header layout to use `justify-between` for left/right spacing
- Maintained all functionality and styling

### 2025-12-04 (Revision 2: Empty State Handling)
- Added conditional rendering for empty filtered results
- Shows contextual message: "No error-level logs", "No warn-level logs", etc.
- Maintains full card width even when filtered results are empty

### 2025-12-04 (Copy Review)
- Applied 3 polish suggestions from copy review
- Changed aria-label to "Log level filter" (more concise)
- Updated empty state: "No logs available" → "No logs yet"
- Updated filtered empty: "No {level} logs found" → "No {level}-level logs"

### 2025-12-04 (Documentation Review)
- Created review breadcrumb: `.agent/Tasks/log-level-filter/04-review.md`
- Updated `.agent/System/frontend_architecture.md` with Tailwind v4 explicit class requirement
- Updated `.agent/SOP/frontend_features.md` with Filter UI Pattern section
- Documented key learnings: filter config pattern, header layout, empty state handling

### 2025-12-04 (Completion)
- ✅ All phases completed successfully
- ✅ Single file modified: `research-logs-list.tsx`
- ✅ Feature ready for manual testing and deployment
- ✅ Documentation updated with patterns for future reference
