# Codebase Patterns

> AE-Scientist patterns — a research pipeline platform

## File Organization

### Frontend (Next.js)

```
frontend/src/
├── app/                    # Next.js App Router pages
│   ├── (dashboard)/       # Dashboard route group
│   │   ├── research/      # Research runs pages
│   │   ├── conversations/ # Conversations pages
│   │   └── billing/       # Billing pages
│   └── login/             # Auth pages
├── features/              # Feature modules
│   ├── research/          # Research run feature
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom hooks
│   │   ├── contexts/      # React contexts
│   │   └── utils/         # Feature utilities
│   ├── conversation/      # Conversation feature
│   ├── project-draft/     # Draft editing feature
│   └── model-selector/    # LLM model selection
├── shared/                # Cross-feature shared code
│   ├── components/        # Shared UI components
│   ├── lib/               # Utility libraries
│   └── providers/         # React providers
└── types/                 # TypeScript types
    └── api.gen.ts         # Auto-generated from OpenAPI
```

### Backend (FastAPI)

```
server/app/
├── api/                   # FastAPI routers
│   ├── auth.py           # Auth endpoints
│   ├── conversations.py  # Conversation CRUD
│   ├── research_runs.py  # Research run endpoints
│   ├── research_pipeline_runs.py  # Pipeline management
│   ├── billing.py        # Stripe billing
│   └── files.py          # File uploads
├── models/               # Pydantic models
│   ├── research_pipeline.py  # Pipeline models
│   ├── conversations.py      # Conversation models
│   └── billing.py            # Billing models
├── services/             # Business logic
│   ├── database/         # Database access layer
│   │   ├── base.py       # Connection pooling
│   │   ├── conversations.py
│   │   ├── research_pipeline_runs.py
│   │   └── billing.py
│   ├── research_pipeline/  # RunPod management
│   └── scraper/            # Chat import parsers
├── middleware/           # Auth middleware
└── config.py             # Settings
```

### Research Pipeline

```
research_pipeline/ai_scientist/
├── treesearch/           # Research tree search
│   ├── stages/           # Pipeline stages
│   └── utils/            # Tree utilities
├── ideation/             # Idea generation
├── llm/                  # LLM clients
├── perform_writeup.py    # Paper generation
├── perform_plotting.py   # Visualization
└── perform_llm_review.py # Auto review
```

## Naming Conventions

| Type            | Pattern                         | Example                                |
| --------------- | ------------------------------- | -------------------------------------- |
| Components      | PascalCase                      | `ResearchHistoryCard.tsx`              |
| Hooks           | camelCase, use\* prefix         | `useResearchRunDetails.ts`             |
| API Routes      | kebab-case URL, snake_case file | `/research-runs/` → `research_runs.py` |
| Pydantic Models | PascalCase                      | `ResearchRunListItem`                  |
| DB Functions    | snake_case                      | `list_all_research_pipeline_runs`      |
| Feature Folders | kebab-case                      | `project-draft/`, `model-selector/`    |

## Frontend Patterns

### Hook Pattern (React Query + apiFetch)

```typescript
// frontend/src/features/research/hooks/useResearchRunDetails.ts
export function useResearchRunDetails({ runId }: Options): Return {
  const [details, setDetails] = useState<ResearchRunDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // SSE for real-time updates
  const { isConnected, reconnect } = useResearchRunSSE({
    runId,
    enabled: !!conversationId && details?.run.status === "running",
    onInitialData: handleInitialData,
    onStageProgress: handleStageProgress,
  });

  return { details, loading, error, isConnected };
}
```

### API Client Pattern

```typescript
// frontend/src/shared/lib/api-client.ts
export async function apiFetch<T>(
  path: string,
  options?: ApiFetchOptions,
): Promise<T> {
  const response = await fetch(buildRequestUrl(path), {
    ...fetchOptions,
    credentials: "include", // Cookie auth
    headers: { "Content-Type": "application/json", ...headers },
  });

  if (!response.ok) {
    if (response.status === 401) window.location.href = "/login";
    throw new ApiError(response.status, `HTTP ${response.status}`);
  }
  return response.json();
}
```

### Component Structure

```typescript
// Feature component pattern
interface Props {
  runId: string;
}

export function ResearchRunHeader({ runId }: Props) {
  // 1. Hooks first
  const { details, loading } = useResearchRunDetails({ runId });

  // 2. Early returns
  if (loading) return <Skeleton />;

  // 3. Derived state
  const isRunning = details?.run.status === "running";

  // 4. Handlers
  const handleStop = async () => { /* ... */ };

  // 5. Render
  return <div>...</div>;
}
```

## Backend Patterns

### FastAPI Router Pattern

```python
# server/app/api/research_runs.py
router = APIRouter(prefix="/research-runs", tags=["research-runs"])

@router.get("/", response_model=ResearchRunListResponse)
def list_research_runs(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str = Query(None),
) -> ResearchRunListResponse:
    user = get_current_user(request)
    db = get_database()
    rows, total = db.list_all_research_pipeline_runs(limit=limit, offset=offset, user_id=user.id)
    return ResearchRunListResponse(items=[_row_to_list_item(row) for row in rows], total=total)
```

### Database Service Pattern

```python
# server/app/services/database/base.py
class BaseDatabaseManager(ConnectionProvider):
    _pool: ThreadedConnectionPool | None = None

    @contextmanager
    def _get_connection(self) -> Iterator[connection]:
        conn = BaseDatabaseManager._pool.getconn()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
        finally:
            BaseDatabaseManager._pool.putconn(conn)
```

### Pydantic Model Pattern

```python
# server/app/models/research_pipeline.py
class ResearchRunListItem(BaseModel):
    run_id: str
    status: str
    idea_title: str
    current_stage: str | None
    progress: float | None
    created_at: str
```

## Testing Patterns

### Python (pytest)

```python
# server/tests/test_*.py
@pytest.mark.asyncio
async def test_list_research_runs():
    response = await client.get("/research-runs/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
```

### TypeScript (Vitest)

```typescript
// orchestrator/tests/*.test.ts
import { describe, it, expect } from "vitest";

describe("component", () => {
  it("should render", () => {
    // test implementation
  });
});
```

## Key Integration Points

| Flow         | Path                                                                                       |
| ------------ | ------------------------------------------------------------------------------------------ |
| Auth         | Google OAuth → Cookie → `middleware/auth.py` → `get_current_user()`                        |
| Research Run | Frontend SSE → `research_pipeline_events.py` → RunPod webhook                              |
| Type Safety  | `server/openapi.json` → `npm run gen:api-types` → `types/api.gen.ts`                       |
| Real-time    | `useResearchRunSSE` → EventSource → `/conversations/{id}/idea/research-run/{runId}/events` |

## Discovered Patterns

| Pattern            | Location                    | Usage                  |
| ------------------ | --------------------------- | ---------------------- |
| Feature modules    | `frontend/src/features/`    | Colocate feature code  |
| SSE updates        | `useResearchRunSSE` hook    | Real-time run progress |
| Connection pooling | `BaseDatabaseManager`       | Shared DB pool         |
| OpenAPI types      | `api.gen.ts`                | Type-safe API calls    |
| Cookie auth        | `apiFetch` with credentials | Session management     |
