# Reusable Assets Inventory

## Agent
codebase-analyzer

## Timestamp
2025-12-04 14:45

## Feature Requirements Summary
The FinalPdfBanner component needs to:
1. Display final PDF download (artifact_type="paper_pdf" with "final" in filename)
2. Display workspace archive download (artifact_type="workspace_archive", .zip file)
3. Use emerald theme styling (matching orchestrator)
4. Show file sizes formatted nicely
5. Integrate with the research run detail page

---

## MUST REUSE (Exact Match Found)

These assets already exist and MUST be used instead of creating new ones:

### Frontend

| Need | Existing Asset | Location | Import Statement |
|------|----------------|----------|------------------|
| File size formatting | `formatFileSize` | `/frontend/src/shared/lib/fileUtils.ts` | `import { formatFileSize } from "@/shared/lib/fileUtils"` |
| API base URL config | `config.apiBaseUrl` | `/frontend/src/shared/lib/config.ts` | `import { config } from "@/shared/lib/config"` |
| CSS class merging | `cn` | `/frontend/src/shared/lib/utils.ts` | `import { cn } from "@/shared/lib/utils"` |
| Relative time formatting | `formatRelativeTime` | `/frontend/src/shared/lib/date-utils.ts` | `import { formatRelativeTime } from "@/shared/lib/date-utils"` |

### Icons (Lucide React)
Already used throughout the codebase. Use these icons for the banner:

| Need | Icon | Import Statement |
|------|------|------------------|
| PDF file icon | `FileText` | `import { FileText } from "lucide-react"` |
| Download icon | `Download` | `import { Download } from "lucide-react"` |
| Archive icon | `Package` | `import { Package } from "lucide-react"` |
| Alternative archive | `FolderArchive` | `import { FolderArchive } from "lucide-react"` |

Note: The run detail page already imports `FileText`, `Download`, and `Package` from lucide-react.

---

## CONSIDER REUSING (Similar Found)

These assets are similar and might be adaptable:

### Frontend

| Need | Similar Asset | Location | Notes |
|------|---------------|----------|-------|
| ArtifactMetadata type | Interface in page.tsx | `/frontend/src/app/(dashboard)/research/[runId]/page.tsx` (lines 78-86) | Same interface defined in useResearchRunSSE.ts (lines 52-60) - could extract to shared types |
| Download link pattern | Artifact download in page.tsx | `/frontend/src/app/(dashboard)/research/[runId]/page.tsx` (lines 525-531) | Uses `<a href={config.apiBaseUrl + download_path}>` pattern - reuse this exact pattern |
| Emerald status badge | getStatusBadge "completed" | `/frontend/src/features/research/utils/research-utils.tsx` (lines 54-61) | Uses `bg-emerald-500/15 text-emerald-400` - same color palette |
| Card styling pattern | ResearchHistoryCard | `/frontend/src/features/research/components/ResearchHistoryCard.tsx` | Uses rounded border, slate background - reference for consistent styling |

### Reference Implementation

| Asset | Location | Notes |
|-------|----------|-------|
| FinalPdfBanner (Orchestrator) | `/orchestrator/components/FinalPdfBanner.tsx` | Primary reference for visual design and emerald theme. Uses presign API (different from frontend's direct download_path) |

---

## CREATE NEW (Nothing Found)

These need to be created as no existing solution was found:

| Need | Suggested Location | Notes |
|------|-------------------|-------|
| FinalPdfBanner component | `/frontend/src/features/research/components/FinalPdfBanner.tsx` | New component following orchestrator visual design |

---

## CONSIDER EXTRACTING TO SHARED

These assets are duplicated and could be generalized for reuse:

| Current Location | Asset | Suggested New Location | Why |
|------------------|-------|------------------------|-----|
| `page.tsx` line 130-136 | `formatBytes` function | Already exists in `/frontend/src/shared/lib/fileUtils.ts` as `formatFileSize` | **Use existing `formatFileSize` instead of duplicating** |
| `page.tsx` line 138-145 | `formatRelativeTime` function | Already exists in `/frontend/src/shared/lib/date-utils.ts` | **Use existing import instead of duplicating** |
| `page.tsx` lines 78-86 | `ArtifactMetadata` interface | `/frontend/src/types/research.ts` | Interface duplicated in page.tsx and useResearchRunSSE.ts - could be extracted |

---

## Patterns Already Established

Document existing patterns the feature should follow:

### State Management Pattern
The run detail page uses:
- SSE (Server-Sent Events) via `useResearchRunSSE` hook for real-time artifact updates
- Local component state with `useState` for `details.artifacts` array
- Callbacks for handling incoming artifact events

FinalPdfBanner is **stateless** - it receives `artifacts` as props from parent.

### Download Pattern
Existing artifact download in page.tsx (lines 525-531):
```typescript
<a
  href={`${config.apiBaseUrl}${artifact.download_path}`}
  className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
>
  <Download className="h-4 w-4" />
  Download
</a>
```

Use this same pattern for FinalPdfBanner downloads (not the orchestrator's presign approach).

### Component Structure Pattern
Research feature components follow:
- PascalCase file names (e.g., `ResearchHistoryCard.tsx`)
- "use client" directive at top
- Props interface defined inline or imported
- Export named function component

### Emerald Theme Pattern (From Orchestrator)
Reference: `/orchestrator/components/FinalPdfBanner.tsx`
```
- Container: border-emerald-800 bg-gradient-to-r from-emerald-950/50 to-emerald-900/30
- Icon backgrounds: bg-emerald-500/20
- Icon color: text-emerald-400
- Title: text-emerald-100
- Subtitle: text-emerald-300/80
- Download cards: border-emerald-700/50 bg-emerald-950/30
- Download buttons: border-emerald-600 bg-emerald-500/20 text-emerald-100
```

### Icon Usage Pattern
The codebase consistently uses lucide-react icons with:
- `h-5 w-5` for standard size
- `h-4 w-4` for smaller/button contexts
- Wrapped in styled div for icon backgrounds

---

## For Architect
Key reusability requirements:
1. **DO NOT** create new: `formatBytes` function (use existing `formatFileSize` from fileUtils.ts)
2. **DO NOT** create new: `formatRelativeTime` function (use existing from date-utils.ts)
3. **REUSE** from: `@/shared/lib/config` for API base URL
4. **REUSE** from: `lucide-react` for icons (FileText, Download, Package)
5. **FOLLOW** patterns from: orchestrator FinalPdfBanner for emerald theme
6. **FOLLOW** patterns from: page.tsx for download link implementation

## For Executor
Before implementing ANY utility/hook/component:
1. Check this inventory first
2. Search the codebase if not listed
3. Only create new if confirmed nothing exists

Key Implementation Notes:
- Use `formatFileSize` from `@/shared/lib/fileUtils` instead of creating new `formatBytes`
- Use `<a href>` pattern for downloads (not fetch + presign like orchestrator)
- Match orchestrator emerald theme exactly for visual consistency
- Component location: `/frontend/src/features/research/components/FinalPdfBanner.tsx`
