# Task Context: Frontend Final PDF Banner

## Original Request
Add a FinalPdfBanner-style component to the frontend research run page (`/research/[runId]/page.tsx`) to prominently display final PDF and tar.gz downloads when available, similar to how the orchestrator does it.

## Orchestrator
Feature Planner Agent

## Timestamp
2025-12-04

## Initial Analysis

### Current State
The frontend research run detail page at `/frontend/src/app/(dashboard)/research/[runId]/page.tsx`:
- Uses SSE for real-time updates via `useResearchRunSSE` hook
- Maintains artifacts array in state with `ArtifactMetadata` type
- Currently displays artifacts in a simple list format at the bottom of the page
- Has `formatBytes` utility already defined locally

### Artifact Schema (Frontend)
```typescript
interface ArtifactMetadata {
  id: number;
  artifact_type: string;
  filename: string;
  file_size: number;
  file_type: string;
  created_at: string;
  download_path: string;
}
```

### Reference Implementation (Orchestrator)
The orchestrator has `FinalPdfBanner.tsx` that:
- Takes `runId` and `artifacts` as props
- Finds final PDF artifact (filename contains "final" and ends with ".pdf")
- Finds tar.gz artifact (filename ends with ".tar.gz")
- Shows emerald-themed banner with download buttons
- Uses presign API for downloads (different from frontend's direct download_path)

### Key Differences Between Frontend and Orchestrator
| Aspect | Frontend | Orchestrator |
|--------|----------|--------------|
| Artifact field for filename | `filename` | `key` |
| Download mechanism | Direct `download_path` redirect | Presign endpoint |
| File size field | `file_size` | `size` |

## Requirements Summary
1. Create `FinalPdfBanner` component for frontend
2. Place prominently at top of run page (after header, before other content)
3. Show final PDF download when available
4. Show experiment archive (tar.gz) download when available
5. Match emerald visual theme of orchestrator
6. Use frontend's artifact schema and download mechanism
7. Only show when at least one final artifact is available
