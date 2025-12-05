# Architecture Phase

## Agent
feature-architecture-expert

## Timestamp
2025-12-04 15:00 (Updated: 2025-12-04 - Post page.tsx refactor)

## Input Received
- Context: `.agent/Tasks/frontend-final-pdf-banner/00-context.md`
- Planning: `.agent/Tasks/frontend-final-pdf-banner/01-planning.md`
- PRD: `.agent/Tasks/frontend-final-pdf-banner/PRD.md`
- Reusable Assets: `.agent/Tasks/frontend-final-pdf-banner/01a-reusable-assets.md`

## ⚠️ IMPORTANT: Post-Refactor Update

The page.tsx has been refactored to use modular components. Key changes:

1. **Types centralized**: `ArtifactMetadata` now lives in `@/types/research.ts`
2. **Component folder**: New `run-detail/` subfolder with barrel exports
3. **Hook extracted**: `useResearchRunDetails` manages all state
4. **Page is now minimal**: Just imports components and wires them together

### New Project Structure
```
frontend/src/features/research/
├── components/
│   ├── run-detail/
│   │   ├── index.ts                    # Barrel exports
│   │   ├── research-artifacts-list.tsx
│   │   ├── research-logs-list.tsx
│   │   ├── research-run-details-grid.tsx
│   │   ├── research-run-error.tsx
│   │   ├── research-run-header.tsx
│   │   ├── research-run-stats.tsx
│   │   ├── research-stage-progress.tsx
│   │   ├── stat-card.tsx
│   │   └── final-pdf-banner.tsx        # ← NEW (to be created)
│   └── ...other components
└── hooks/
    ├── useResearchRunDetails.ts        # Manages all state + SSE
    └── useResearchRunSSE.ts
```

## Key Decisions from Planning (UPDATED)
From `01-planning.md`:
1. **Single stateless component** - No hooks needed since parent provides artifacts via SSE
2. **Feature location** - `features/research/components/run-detail/` (following new pattern)
3. **No runId prop needed** - Frontend uses direct `download_path` (unlike orchestrator's presign API)
4. **Simple download mechanism** - `<a href>` with `target="_blank"` instead of fetch + presign

---

## Reusability (CRITICAL SECTION)

### Assets Being REUSED (Do NOT Recreate)
| Asset | Source Location | Used For |
|-------|-----------------|----------|
| `formatFileSize` | `@/shared/lib/fileUtils` | Display file size (e.g., "4.5 MB") |
| `config.apiBaseUrl` | `@/shared/lib/config` | Construct full download URL |
| `FileText` icon | `lucide-react` | PDF file indicator |
| `Download` icon | `lucide-react` | Download button indicator |
| `FolderArchive` icon | `lucide-react` | Archive file indicator |

### Assets Being CREATED (New)
| Asset | Location | Justification |
|-------|----------|---------------|
| `FinalPdfBanner` component | `features/research/components/run-detail/final-pdf-banner.tsx` | Feature-specific banner, follows new modular pattern |

### Imports Required
```typescript
// Types (centralized in @/types/research.ts)
import type { ArtifactMetadata } from "@/types/research";

// From shared utilities
import { formatFileSize } from "@/shared/lib/fileUtils";
import { config } from "@/shared/lib/config";

// From lucide-react
import { FileText, Download, FolderArchive } from "lucide-react";
```

---

## SOLID Analysis (CRITICAL SECTION)

### Principles Applied in This Design

| Principle | How Applied |
|-----------|-------------|
| **SRP** | Component has single responsibility: render download banner for final artifacts. No data fetching, no state management. |
| **OCP** | Artifact detection logic can be extended by modifying detection functions without changing render logic. Banner styling uses Tailwind classes that can be overridden. |
| **LSP** | N/A - No inheritance hierarchy in this component |
| **ISP** | Props interface is minimal: only `artifacts` array required. No unused props. |
| **DIP** | Component depends on `ArtifactMetadata` interface (abstraction), not concrete implementation. Download URL construction delegated to config. |

### SOLID Violations Found in Existing Code

✅ **None found after refactor!**

The recent refactoring addressed previous technical debt:
- `ArtifactMetadata` is now centralized in `@/types/research.ts`
- `formatBytes` duplication has been removed (use `formatFileSize` from shared utils)
- Components are properly separated with single responsibilities

### Refactoring Plan

**Priority: None** - No refactoring needed before implementation

### Architecture Decisions for SOLID Compliance

1. **Component Separation (SRP)**
   - Data source: Parent page via SSE (no fetching in banner)
   - Artifact detection: Pure functions inside component
   - Rendering: Single functional component

2. **Extensibility Points (OCP)**
   - Detection logic uses simple predicates that can be modified
   - Styling uses Tailwind utility classes

3. **Dependency Injection (DIP)**
   - Props interface defines contract
   - URL construction uses config abstraction
   - File size formatting delegated to shared utility

---

## Reasoning

### Frontend Architecture
- **Pattern**: Stateless presentational component
- **Rationale**: Component receives all data via props from parent, no internal state or side effects needed
- **SOLID alignment**: SRP (single render responsibility), ISP (minimal props interface)
- **Reference**: Similar to `ResearchHistoryCard.tsx` pattern in same feature

### Data Flow (Updated for refactored architecture)
```
┌─────────────────────────────────────────────────────────────┐
│ page.tsx (Research Run Detail) - Minimal orchestration       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ useResearchRunDetails hook                               │ │
│ │ - Manages all state (details, loading, error, etc.)     │ │
│ │ - Uses useResearchRunSSE internally                      │ │
│ │ - Returns { details, ...controls }                       │ │
│ └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
│       details.artifacts   │                                  │
│                           ▼                                  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Component render order:                                   │ │
│ │  1. ResearchRunHeader                                    │ │
│ │  2. ResearchRunError (conditional)                       │ │
│ │  3. FinalPdfBanner (NEW - conditional)                   │ │
│ │  4. ResearchRunStats                                     │ │
│ │  5. ResearchStageProgress (conditional)                  │ │
│ │  6. ResearchArtifactsList                                │ │
│ │  7. ResearchLogsList                                     │ │
│ │  8. ResearchRunDetailsGrid                               │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Key Interfaces
```typescript
// Type from @/types/research.ts (centralized)
interface ArtifactMetadata {
  id: number;
  artifact_type: string;
  filename: string;
  file_size: number;
  file_type: string;
  created_at: string;
  download_path: string;
}

// Component props
interface FinalPdfBannerProps {
  artifacts: ArtifactMetadata[];
}
```

---

## Detailed File Structure

### Frontend (NEW FILE)
```
frontend/src/features/research/components/run-detail/
├── index.ts                  # MODIFIED - Add FinalPdfBanner export
└── final-pdf-banner.tsx      # NEW - Final results download banner
```

### File Modified
```
frontend/src/features/research/components/run-detail/index.ts
  - Add export for FinalPdfBanner

frontend/src/app/(dashboard)/research/[runId]/page.tsx
  - Add import for FinalPdfBanner
  - Add <FinalPdfBanner artifacts={artifacts} /> in render
```

---

## Component Specifications

### FinalPdfBanner

**Purpose**: Display prominent download banner for final PDF and workspace archive when available.

**Props Interface**:
```typescript
interface FinalPdfBannerProps {
  artifacts: ArtifactMetadata[];
}
```

**Dependencies**:
- `@/types/research` - `ArtifactMetadata` type
- `@/shared/lib/fileUtils` - `formatFileSize`
- `@/shared/lib/config` - `config.apiBaseUrl`
- `lucide-react` - `FileText`, `Download`, `FolderArchive`

**Internal Logic**:
```typescript
// Detection logic
const finalPdf = artifacts.find(
  (a) => a.artifact_type === "paper_pdf" &&
         a.filename.toLowerCase().includes("final")
);

const workspaceArchive = artifacts.find(
  (a) => a.artifact_type === "workspace_archive"
);

// Early return if no final artifacts
if (!finalPdf && !workspaceArchive) return null;
```

**Styling Reference** (from orchestrator):
```
Container:
- border border-emerald-800
- bg-gradient-to-r from-emerald-950/50 to-emerald-900/30
- rounded-lg p-6

Header icon:
- h-10 w-10 rounded-full bg-emerald-500/20
- Icon: h-6 w-6 text-emerald-400

Title: text-base font-semibold text-emerald-100
Subtitle: text-sm text-emerald-300/80

Download cards:
- rounded-lg border border-emerald-700/50 bg-emerald-950/30 p-4

Download buttons:
- rounded border border-emerald-600 bg-emerald-500/20
- px-4 py-2 text-sm font-medium text-emerald-100
- hover:bg-emerald-500/30
```

**Download Pattern** (from page.tsx line 525-531):
```typescript
<a
  href={`${config.apiBaseUrl}${artifact.download_path}`}
  className="..." // emerald button styles
>
  <Download className="h-4 w-4" />
  Download
</a>
```

---

## Integration Instructions

### 1. Add Export to index.ts

In `frontend/src/features/research/components/run-detail/index.ts`:
```typescript
export { FinalPdfBanner } from "./final-pdf-banner";
```

### 2. Import Component in page.tsx

Update import at top of file:
```typescript
import {
  FinalPdfBanner,  // ← ADD THIS
  ResearchArtifactsList,
  ResearchLogsList,
  ResearchRunDetailsGrid,
  ResearchRunError,
  ResearchRunHeader,
  ResearchRunStats,
  ResearchStageProgress,
} from "@/features/research/components/run-detail";
```

### 3. Render Component

Add after error message section (line ~79) and before stats (line ~81):
```typescript
{run.error_message && <ResearchRunError message={run.error_message} />}

{/* Final Results Banner - NEW */}
<FinalPdfBanner artifacts={artifacts} />

<ResearchRunStats
  latestProgress={latestProgress}
  gpuType={run.gpu_type}
  artifactsCount={artifacts.length}
/>
```

### 4. Placement Rationale
- After header: User sees run status first
- After error: Error visibility takes precedence
- Before stats/progress: Final results are the most important actionable item for completed runs

---

## For Next Phase (Implementation)

### Recommended Implementation Order
1. Create `FinalPdfBanner.tsx` component file
2. Implement artifact detection logic
3. Implement emerald-themed UI (reference orchestrator styling)
4. Add download links using `<a href>` pattern
5. Import and integrate in page.tsx

### Type Dependencies
- `ArtifactMetadata` interface - Import from `@/types/research` (centralized types)

### SOLID Considerations
- Keep component focused on rendering only (SRP)
- Use props interface as contract (DIP)
- Avoid adding state unless absolutely necessary

### Refactoring Prerequisites
- None required - existing code is acceptable

### Critical Considerations
1. **Use `formatFileSize` from `@/shared/lib/fileUtils`** - Do NOT create new `formatBytes` function
2. **Match orchestrator emerald theme exactly** - Use same Tailwind classes
3. **Use `<a href>` for downloads** - NOT fetch + presign like orchestrator
4. **Detection logic**:
   - Final PDF: `artifact_type === "paper_pdf"` AND `filename.toLowerCase().includes("final")`
   - Workspace Archive: `artifact_type === "workspace_archive"` (always .zip)
5. **Conditional rendering** - Return `null` if neither artifact available

---

## Summary

```
FILE TO CREATE:
  /frontend/src/features/research/components/run-detail/final-pdf-banner.tsx

FILES TO MODIFY:
  /frontend/src/features/research/components/run-detail/index.ts
  - Add export for FinalPdfBanner

  /frontend/src/app/(dashboard)/research/[runId]/page.tsx
  - Add FinalPdfBanner to import
  - Add <FinalPdfBanner artifacts={artifacts} /> after error section

REUSE (DO NOT CREATE):
  - ArtifactMetadata type from @/types/research
  - formatFileSize from @/shared/lib/fileUtils
  - config.apiBaseUrl from @/shared/lib/config
  - FileText, Download, FolderArchive from lucide-react

SOLID COMPLIANCE:
  - SRP: Single render responsibility
  - OCP: Extensible detection logic
  - ISP: Minimal props interface
  - DIP: Depends on abstractions (interface, config)

ESTIMATED SIZE: ~80-100 lines
```

---

## Approval Status
- [ ] Pending approval
- [ ] Approved - proceed to Implementation
- [ ] Modified - see feedback below

Waiting for your approval before continuing...
