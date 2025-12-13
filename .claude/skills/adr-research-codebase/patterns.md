# Codebase Patterns

> AE-Scientist-specific patterns discovered through research

## File Organization

**Root Structure:**

```
AE-Scientist/
├── frontend/              # Next.js 16 web app (React 19)
│   └── src/
│       ├── features/      # Feature-based modules
│       ├── shared/        # Shared hooks, lib, components
│       ├── types/         # TypeScript types
│       └── app/           # Next.js app router
├── server/                # FastAPI backend (Python 3.12)
│   └── app/
│       ├── api/           # Route handlers
│       ├── services/      # Business logic
│       ├── models/        # Pydantic models
│       └── middleware/    # Auth, etc.
├── orchestrator/          # Next.js orchestration (TypeScript)
│   ├── app/api/           # API routes
│   ├── lib/               # Repos, services, schemas, state
│   └── components/        # React components
├── research_pipeline/     # AI scientist ML pipeline (Python)
│   └── ai_scientist/
│       ├── treesearch/    # BFTS + stages
│       ├── llm/           # LLM integrations
│       └── telemetry/     # Event tracking
├── adr/                   # Architecture Decision Records
│   ├── decisions/         # ADR documents
│   └── tasks/             # Task research/plans
└── .claude/               # Agent system
    ├── agents/            # Agent definitions
    ├── commands/          # Slash commands
    └── skills/            # Reusable skills
```

## Naming Conventions

| Type                 | Pattern                 | Example                         |
| -------------------- | ----------------------- | ------------------------------- |
| Components           | PascalCase              | `ResearchHistoryList.tsx`       |
| Hooks                | camelCase, use\* prefix | `useRecentResearch.ts`          |
| TypeScript Types     | camelCase               | `research.ts`                   |
| API Routes (Next.js) | route.ts                | `runs/[id]/route.ts`            |
| Schemas (Zod)        | PascalCaseZ suffix      | `RunZ`, `StageZ`                |
| Repositories         | \*.repo.ts              | `runs.repo.ts`                  |
| FastAPI Routes       | snake_case.py           | `research_pipeline_runs.py`     |
| Python Services      | snake_case.py           | `runpod_manager.py`             |
| Pydantic Models      | snake_case.py           | `research_pipeline.py`          |
| Python Classes       | PascalCase              | `RunPodManager`                 |
| ADR Decisions        | YYYYMMDD_HHMMSS-slug.md | `20251212_120944-adr-system.md` |
| Agent Definitions    | agent-name.md           | `adr-research-agent.md`         |

## React Query Hook Pattern

```typescript
// frontend/src/features/research/hooks/useRecentResearch.ts:25-39
export function useRecentResearch(): UseRecentResearchReturn {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["recent-research"],
    queryFn: fetchRecentResearch,
    staleTime: 30 * 1000,
  });

  return {
    researchRuns: data ?? [],
    isLoading,
    error: error instanceof Error ? error.message : error ? "..." : null,
    refetch,
  };
}
```

## Repository Pattern

```typescript
// orchestrator/lib/repos/runs.repo.ts:12-32
export async function createRun(run: Run): Promise<Run> {
  const dto = RunZ.parse(run);
  const db = await getDb();
  await db
    .collection<Run>(COLLECTION)
    .insertOne(dto as OptionalUnlessRequiredId<Run>);
  return dto;
}

export async function updateRun(
  id: string,
  patch: Partial<Run>,
): Promise<void> {
  const db = await getDb();
  const updateDoc = { ...patch, updatedAt: new Date() };
  await db
    .collection<Run>(COLLECTION)
    .updateOne({ _id: id }, { $set: updateDoc });
}
```

## Schema Validation Pattern

```typescript
// orchestrator/lib/schemas/run.ts:9-14
const StageProgressZ = z.preprocess(
  (val: any) => {
    // Defensive: Clamp progress to [0, 1]
    if (val && typeof val === "object" && typeof val.progress === "number") {
      return { ...val, progress: Math.max(0, Math.min(val.progress, 1)) };
    }
    return val;
  },
  z.object({
    /* ... */
  }),
);
```

## FastAPI Route Pattern

```python
# server/app/api/research_pipeline_runs.py:1-50
from fastapi import APIRouter, HTTPException, Request, Depends
from app.middleware.auth import get_current_user
from app.models import ResearchRunDetailsResponse
from app.services import get_database
from app.services.database import DatabaseManager

router = APIRouter()

@router.get("/research-runs/{run_id}")
async def get_research_run(
    run_id: str,
    request: Request,
    current_user = Depends(get_current_user),
    db: DatabaseManager = Depends(get_database)
):
    # Implementation
```

## Service Pattern

```python
# server/app/services/research_pipeline/runpod_manager.py:22-30
class RunPodError(Exception):
    """Custom exception for RunPod-related errors."""
    pass

class RunPodManager:
    """Manages RunPod GPU instance lifecycle."""

    def __init__(self, config: dict):
        # Implementation
```

## Data Flow Patterns

**Research Run Lifecycle:**

```
Frontend (useRecentResearch.ts:8)
  → Server API (research_pipeline_runs.py:1)
  → Database Service (research_pipeline_runs.py:34)
  → RunPod Manager (runpod_manager.py:441)
  → Research Pipeline (treesearch/perform_experiments_bfts_with_agentmanager.py)
  → Telemetry (telemetry/event_persistence.py)
  → SSE Stream (useResearchRunSSE.ts:122)
  → UI Updates (research-pipeline-stages.tsx:244)
```

**Progress Tracking:**

```
Pipeline Stage → Telemetry → Server Ingest → Database
  → SSE Endpoint → Frontend Hook → State Update → Component Render
```

## ADR Workflow Pattern

```
/adr-feature "feature name"
  → decision-support-agent (decision-brief.md)
  → ux-strategy-agent (ux-strategy.md) [if frontend]
  → research-agent (research.md)
  → planner-agent (plan.md)
  → executor-agent (code)
  → review-agent (compliance check)
```

## Discovered Patterns

| Pattern                | Location                                            | Usage                                                |
| ---------------------- | --------------------------------------------------- | ---------------------------------------------------- |
| Feature-based org      | `frontend/src/features/`                            | Each has components/, hooks/, utils/, contexts/      |
| Repository pattern     | `orchestrator/lib/repos/*.repo.ts`                  | Data access abstraction                              |
| Schema preprocessing   | `orchestrator/lib/schemas/run.ts:24-48`             | Normalize/validate before parsing                    |
| Service layering       | `server/app/services/`                              | database/, scraper/, research_pipeline/ subdomains   |
| Event-driven telemetry | `research_pipeline/ai_scientist/telemetry/`         | Pipeline stages emit typed events                    |
| SSE streaming          | Server API → Frontend hooks                         | Real-time progress updates                           |
| Stage-based pipeline   | `research_pipeline/ai_scientist/treesearch/stages/` | stage1-4 implementations                             |
| ADR workflow           | `adr/tasks/{timestamp}-{slug}/`                     | research.md → plan.md → execution                    |
| Agent delegation       | `.claude/agents/`                                   | Specialized agents for research, planning, execution |
