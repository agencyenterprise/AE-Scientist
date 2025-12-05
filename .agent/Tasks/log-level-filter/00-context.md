# Task Context: Log Level Filter

## Source
User request for feature implementation

## Feature Request
Add a log level filter to the research logs list component (`research-logs-list.tsx`) to allow users to filter logs by severity level (ALL, INFO, WARN, ERROR).

## Target Component
`frontend/src/features/research/components/run-detail/research-logs-list.tsx`

## UI Reference
The user provided a reference showing horizontal filter buttons:
- "all" button (active/selected style)
- "info" button
- "warn" button
- "error" button

These buttons should appear in a horizontal row near the "Logs" title.

## Current State
The component currently:
- Displays all logs without filtering
- Shows timestamp, log level (uppercase), and message
- Uses `getLogLevelColor()` utility for level-based coloring
- Receives `logs: LogEntry[]` as props

## Related Files
- `frontend/src/features/research/components/run-detail/research-logs-list.tsx`
- `frontend/src/features/research/utils/research-utils.tsx` (contains `getLogLevelColor`)
- `frontend/src/types/research.ts` (contains `LogEntry` type)

## Constraints
- Must follow existing frontend architecture patterns
- Should use local component state (useState) for filter state
- No backend changes required
- Filter should be purely client-side
