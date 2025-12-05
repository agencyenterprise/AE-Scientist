# Planning Phase

## Agent
feature-planner

## Timestamp
2025-12-04 14:30

## Input Received
- Context: `.agent/Tasks/frontend-final-pdf-banner/00-context.md`
- Project docs consulted:
    - `.agent/README.md`
    - `.agent/System/frontend_architecture.md`
    - `.agent/SOP/frontend_features.md`
    - `orchestrator/components/FinalPdfBanner.tsx` (reference implementation)
    - `frontend/src/app/(dashboard)/research/[runId]/page.tsx` (integration target)
    - `frontend/src/features/research/utils/research-utils.tsx` (existing utils)
    - `frontend/src/shared/lib/config.ts` (API config)

## Reasoning

### Why This Approach

1. **Single Component vs Hook+Component**:
   - Chose single component because the logic is simple (artifact filtering + conditional render)
   - No need for separate hook since there's no complex state management or API calls
   - The parent page already provides artifacts via SSE

2. **Feature Location**:
   - Placing in `features/research/components/` because it's research-specific
   - Not in shared components since it's tightly coupled to research artifacts schema

3. **No runId Prop Needed**:
   - Frontend uses direct `download_path` field from artifacts
   - Unlike orchestrator which needs runId for presign API endpoint
   - Simpler API surface

4. **Simpler Download Mechanism**:
   - Frontend artifacts already have `download_path` that redirects to S3
   - No need for presign endpoint complexity
   - Just use `<a href>` with `target="_blank"` instead of click handlers with fetch

### Pattern Selection
- Chose pattern: **Simple presentational component**
- Because: Component has no internal state, just receives props and renders UI
- Reference: Similar to `ResearchHistoryCard.tsx` in the same feature

### Dependencies Identified
- **config.apiBaseUrl**: Required to construct full download URLs from `download_path`
- **Lucide icons**: `FileText`, `Download`, `Archive` (or similar) for visual consistency
- **ArtifactMetadata type**: Already defined in page, will import or re-define locally

### Risks & Considerations
- **Risk 1**: Artifact filename patterns may vary
  - Mitigation: Use case-insensitive matching, same logic as orchestrator
- **Risk 2**: Download path format might change
  - Mitigation: Use existing pattern from current artifacts section in page
- **Risk 3**: Banner might look too prominent when page has errors
  - Mitigation: Only show banner for completed/running runs with artifacts, not for failed runs

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Component location | `features/research/components/` | Research-specific, follows existing feature structure |
| Props interface | `{ artifacts: ArtifactMetadata[] }` | Minimal props, no runId needed |
| Download method | Direct `<a href>` with download_path | Simpler than orchestrator's presign approach, uses existing pattern |
| State management | None (stateless component) | Parent provides all data via props |
| Loading states | None needed | Downloads happen via browser navigation |
| formatBytes | Local function in component | Matches existing pattern in page, avoids over-engineering |

## Output Summary
- PRD created: `.agent/Tasks/frontend-final-pdf-banner/PRD.md`
- Files to create: 1 frontend component
- Files to modify: 1 frontend page
- Estimated complexity: **Simple** - Single component, ~100-150 lines

## For Next Phase (Architecture)

Key considerations for the architect:
1. **Component is self-contained**: No hooks, contexts, or complex state needed
2. **Use existing artifact type**: Can import from page or define locally (prefer local for isolation)
3. **Match orchestrator styling exactly**: Use same Tailwind classes for emerald theme
4. **Integration point**: Add component right after error message section in page, before overview grid

## Implementation Details (Ready for Dev)

Since this is a simple feature, here's the implementation approach:

### FinalPdfBanner.tsx Structure
```typescript
"use client"

import { config } from "@/shared/lib/config"
import { FileText, Archive, Download } from "lucide-react"

interface ArtifactMetadata {
  id: number
  artifact_type: string
  filename: string
  file_size: number
  file_type: string
  created_at: string
  download_path: string
}

interface FinalPdfBannerProps {
  artifacts: ArtifactMetadata[]
}

function formatBytes(bytes: number): string {
  // ... implementation
}

export function FinalPdfBanner({ artifacts }: FinalPdfBannerProps) {
  // Find final PDF: filename contains "final" AND ends with ".pdf"
  const finalPdf = artifacts.find(
    (a) => a.filename.toLowerCase().includes("final") &&
           a.filename.toLowerCase().endsWith(".pdf")
  )

  // Find tar.gz archive
  const tarGz = artifacts.find(
    (a) => a.filename.toLowerCase().endsWith(".tar.gz")
  )

  // Don't render if neither is available
  if (!finalPdf && !tarGz) return null

  // Render emerald-themed banner with download cards
}
```

### Page Integration
```typescript
// In page.tsx, after error message section:
{/* Final Results Banner */}
<FinalPdfBanner artifacts={artifacts} />

{/* Overview Grid */}
<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
  ...
</div>
```

## Approval Status
- [ ] Pending approval
- [ ] Approved - proceed to Architecture
- [ ] Modified - see feedback below

### Feedback (if modified)
{User feedback will be added here}
