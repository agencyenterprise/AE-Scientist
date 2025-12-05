# Frontend Final PDF Banner - Product Requirements Document

## Overview
Add a prominent banner component to the frontend research run detail page that displays download links for the final PDF paper and experiment archive (tar.gz) when these artifacts become available.

## Status
- [x] Planning
- [x] Architecture
- [x] Implementation
- [x] Testing
- [x] Complete

## User Stories
- As a researcher, I want to easily find and download the final PDF paper when my research run completes so that I can review the generated paper
- As a researcher, I want to download the complete experiment archive so that I can access all generated code, logs, and plots
- As a researcher, I want the download options to be prominently displayed so that I don't have to scroll through a long list of artifacts

## Requirements

### Functional
1. **Final PDF Detection**: Identify the final PDF artifact by matching `artifact_type === "paper_pdf"` AND filename containing "final"
2. **Archive Detection**: Identify the workspace archive by matching `artifact_type === "workspace_archive"` (always .zip)
3. **Conditional Display**: Only show the banner when at least one of the final artifacts is available
4. **Download Action**: Clicking download should open the artifact URL in a new tab using the existing `download_path` field
5. **File Size Display**: Show human-readable file size for each artifact
6. **Responsive Layout**: Two-column grid on medium screens, single column on mobile

### Non-Functional
1. **Visual Consistency**: Match the emerald-themed styling of the orchestrator component
2. **Placement**: Display prominently after the header and error message, before the overview grid
3. **Performance**: Component should not cause unnecessary re-renders
4. **Accessibility**: Download buttons should be keyboard accessible and have appropriate labels

## Technical Decisions

Based on project documentation:

### Pattern
- **Feature Organization**: Component will live in `frontend/src/features/research/components/` following the existing research feature structure
- **Naming Convention**: `FinalPdfBanner.tsx` (PascalCase for components)
- **No barrel exports needed**: Component used only in one place (run detail page)

### SOPs Applied
- **Frontend Features SOP**: Component goes in `features/research/components/`
- **Frontend Architecture**: Use kebab-case folder names, PascalCase component files

### Dependencies
- **Existing**: `config.apiBaseUrl` from `@/shared/lib/config` for download URLs
- **Existing**: `formatFileSize` from `@/shared/lib/fileUtils` for file size formatting
- **Existing**: `ArtifactMetadata` interface already defined in the page

## Reusability Analysis

### Existing Assets to REUSE
- [x] `config.apiBaseUrl` from `@/shared/lib/config` - for constructing download URLs
- [x] `formatFileSize` from `@/shared/lib/fileUtils` - for human-readable file sizes
- [x] Lucide icons (`FileText`, `Download`, `FolderArchive`) - already available

### Similar Features to Reference
- **orchestrator/components/FinalPdfBanner.tsx**: Primary reference for visual design and artifact detection logic
- **research-utils.tsx**: Example of research feature utilities pattern

### Needs Codebase Analysis
- [x] No - Simple component with no complex shared dependencies

## Implementation Plan

### Phase 1: Component Creation
- [x] Analyze existing code and requirements (this document)
- [x] Create `final-pdf-banner.tsx` in `frontend/src/features/research/components/run-detail/`
- [x] Implement artifact detection logic (final PDF and workspace archive)
- [x] Implement emerald-themed UI matching orchestrator style
- [x] Add download functionality using `download_path`

### Phase 2: Integration
- [x] Import and add component to `research/[runId]/page.tsx`
- [x] Position after header/error message, before overview grid
- [x] Pass artifacts array as prop

### Phase 3: Testing & Refinement
- [ ] Test with completed research run (has final artifacts)
- [ ] Test with in-progress run (no final artifacts - banner should not show)
- [ ] Verify download functionality works correctly
- [ ] Test responsive layout

## File Structure (Proposed)

```
frontend/src/features/research/
├── components/
│   ├── FinalPdfBanner.tsx        # NEW - Final results banner
│   ├── ResearchBoardHeader.tsx
│   ├── ResearchBoardTable.tsx
│   ├── ResearchHistoryCard.tsx
│   ├── ResearchHistoryEmpty.tsx
│   ├── ResearchHistoryList.tsx
│   ├── ResearchHistorySkeleton.tsx
│   └── ...
├── hooks/
│   ├── useResearchRunSSE.ts
│   └── useRecentResearch.ts
├── utils/
│   └── research-utils.tsx
└── contexts/
    └── ResearchContext.tsx
```

**Modified Files:**
- `frontend/src/app/(dashboard)/research/[runId]/page.tsx` - Import and use FinalPdfBanner

## Component API

```typescript
interface FinalPdfBannerProps {
  artifacts: ArtifactMetadata[];
}

// Usage in page:
<FinalPdfBanner artifacts={artifacts} />
```

**Note**: Unlike orchestrator, we don't need `runId` prop because frontend uses direct `download_path` instead of presign API.

## Visual Design Reference

The component should match the orchestrator's emerald theme:
- Container: `border-emerald-800 bg-gradient-to-r from-emerald-950/50 to-emerald-900/30`
- Icon backgrounds: `bg-emerald-500/20`
- Icon color: `text-emerald-400`
- Title: `text-emerald-100`
- Subtitle: `text-emerald-300/80`
- Download cards: `border-emerald-700/50 bg-emerald-950/30`
- Download buttons: `border-emerald-600 bg-emerald-500/20 text-emerald-100`

## Related Documentation
- `.agent/System/frontend_architecture.md` - Frontend conventions
- `.agent/SOP/frontend_features.md` - Feature organization patterns
- `orchestrator/components/FinalPdfBanner.tsx` - Reference implementation
- `.agent/Tasks/frontend-final-pdf-banner/02-architecture.md` - Architecture details

## Progress Log

### 2025-12-04
- Created initial PRD
- Analyzed orchestrator reference implementation
- Identified differences between frontend and orchestrator artifact schemas
- Determined component placement and integration strategy
- **Architecture phase completed** - See `02-architecture.md` for details
- **Implementation phase completed** - See `03-implementation.md` for details
  - Created `final-pdf-banner.tsx` component (108 lines)
  - Added export to `run-detail/index.ts`
  - Integrated into `page.tsx` after error section
  - TypeScript compilation: No errors
- **S3 Download Fix** - Changed download mechanism from direct `<a href>` to presigned URL pattern
  - Created `useArtifactDownload` hook for presigned URL downloads
  - Updated `FinalPdfBanner` and `ResearchArtifactsList` to use the hook
  - Added backend `/presign` endpoint for secure URL generation
  - Solves AccessDenied errors with S3 redirects
- **Documentation review completed** - See `04-review.md` for details
  - Updated `.agent/SOP/frontend_api_hooks.md` with S3 download pattern
  - Updated `.agent/System/server_architecture.md` with presign endpoint docs
  - Task marked as complete
