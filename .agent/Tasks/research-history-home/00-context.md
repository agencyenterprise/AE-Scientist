# Research History on Home Page - Initial Context

## Agent
orchestrator (initial request)

## Timestamp
2025-12-03

## Original Request
Add "Last 10 hypotheses" history to the home page ("/"). The section should appear underneath the existing Hypothesis card and show the user's individual hypothesis history.

**Important**: Change the verbiage from "hypothesis" to "research" history.

## Reference Implementation
Based on the production site (ai-scientist-v2-production.up.railway.app), the research history section should display:
- The 10 most recent research proposals, arranged chronologically (newest to oldest)
- Each entry shows:
  - **Title**: The research hypothesis/research name
  - **Status badge**: Indicates current state (e.g., "Waiting on ideation", "Running", "Completed")
  - **Timestamp**: When the research was launched
  - **Ideation highlight**: A brief summary or description of the research direction
  - **Action button**: "Relaunch experiment" option for each entry

## Initial Analysis

### Feature Type
Frontend-focused feature with potential backend API requirement

### Existing Infrastructure
1. **Backend API exists**: `/api/research-runs/` endpoint already provides research run listing with pagination, filtering, and all required fields
2. **Frontend types exist**: `ResearchRun` type in `/frontend/src/types/research.ts` already defines all needed fields
3. **Research feature exists**: `/frontend/src/features/research/` has existing components for displaying research runs

### Key Files Identified
- Home page: `/frontend/src/app/(dashboard)/page.tsx`
- Research context: `/frontend/src/features/research/contexts/ResearchContext.tsx`
- Research table component: `/frontend/src/features/research/components/ResearchBoardTable.tsx`
- API adapters: `/frontend/src/shared/lib/api-adapters.ts`
- Research types: `/frontend/src/types/research.ts`

### Complexity Assessment
**Low-Medium complexity** - Most infrastructure exists, primarily needs:
1. A new compact card component for home page (simpler than full research board)
2. A hook to fetch recent 10 research runs for current user
3. Integration into home page below the hypothesis form

## Next Steps
Planning agent to:
1. Analyze existing research components for reuse
2. Design the compact research history card component
3. Define implementation phases
4. Create PRD with status tracking
