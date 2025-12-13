# Decision Brief: fix-stage-progress-display

**Generated:** 2025-12-12T15:51:37
**Keywords:** progress, percentage, iteration, stage, pipeline, display, StageProgress

## Constraints (MUST follow)
1. Always use `@/` for internal imports -> `adr/decisions/20251212_152505-frontend-path-mapping-pattern.md:156`
2. Never use useState + useEffect for SSR guards; use useIsClient -> `adr/decisions/20251212_120946-react-19-ssr-patterns.md:40`
3. Always prefer derived state over synchronized state -> `adr/decisions/20251212_120946-react-19-ssr-patterns.md:42`

## Target Files
- `frontend/src/features/research/components/run-detail/research-stage-progress.tsx:13,21-22` - Shows `progressPercent` and `iteration/max_iterations`
- `frontend/src/features/research/components/run-detail/research-pipeline-stages.tsx:83-92` - StageInfo type with iteration/maxIterations

## Key Context
- Stages 1-4 use early-exit search (stop when good node found)
- `progress.iteration` / `progress.max_iterations` is available in StageProgress type
- Current display: percentage from `progress.progress * 100`
- Fix: Replace percentage with "Iteration X of Y" for transparency

## Reference (read if needed)
- `adr/tasks/20251212_151656-pipeline-stages-progress/research.md` - Full progress system analysis
- `adr/tasks/20251211_162530-stage5-display-fix/progress.md` - Related Stage 5 work

## ADR Quick Refs
| Decision | Status | Key Point |
|----------|--------|-----------|
| `20251212_152505-frontend-path-mapping-pattern.md` | Accepted | Use @/ imports |
| `20251212_120946-react-19-ssr-patterns.md` | Accepted | Derived state, no useEffect syncs |
