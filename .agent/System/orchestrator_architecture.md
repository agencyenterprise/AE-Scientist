# Orchestrator Architecture

## Related Documentation
- [README.md](../README.md) - Documentation index
- [Project Architecture](project_architecture.md) - Overall system architecture

---

## 1. Overview

The orchestrator is a Next.js application that manages experiment lifecycle, RunPod GPU provisioning, event processing, and real-time monitoring for the AE-Scientist platform.

### Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 16.0.0 | React framework with App Router |
| React | 19.2.0 | UI library |
| TypeScript | 5.x | Type-safe JavaScript |
| MongoDB | 6.7.0 | Primary database |
| Redis | ioredis 5.4.1 | Caching, queues, semaphores |
| BullMQ | 5.32.2 | Job queue processing |
| MinIO | 8.0.1 | Object storage for artifacts |
| OpenAI | 4.73.0 | Paper analysis |
| Pino | 9.3.2 | Structured logging |
| Zod | 3.23.8 | Schema validation |
| Tailwind CSS | 4.x | Styling |

### Key Capabilities
- CloudEvents-based event ingestion and processing
- Run state machine with validated transitions
- RunPod GPU provisioning with round-robin fallback
- Real-time log streaming via SSE
- Artifact storage and presigned URL generation
- Human validation workflow
- Paper analysis via LLM

---

## 2. Project Structure

```
orchestrator/
├── app/                          # Next.js App Router
│   ├── layout.tsx               # Root layout with navigation
│   ├── page.tsx                 # Home - hypothesis submission
│   ├── overview/                # Dashboard overview
│   ├── ideation/                # Ideation queue
│   ├── validations/queue/       # Human validation queue
│   ├── runs/[id]/               # Run detail page
│   └── api/                     # API routes
│       ├── ingest/              # Event ingestion
│       ├── runs/                # Run management
│       ├── hypotheses/          # Hypothesis CRUD
│       ├── ideations/           # Ideation requests
│       ├── validations/         # Validation submission
│       ├── artifacts/           # Artifact downloads
│       ├── overview/            # System overview
│       └── health/              # Health check
│
├── components/                   # React components
│   ├── CreateHypothesisForm.tsx
│   ├── HypothesisHistoryList.tsx
│   ├── RunTable.tsx
│   ├── RunDetailClient.tsx
│   ├── StageProgressPanel.tsx
│   ├── PaperAnalysisPanel.tsx
│   ├── ArtifactList.tsx
│   ├── LiveLogViewer.tsx
│   └── ...
│
├── lib/                          # Core business logic
│   ├── config/                  # Environment configuration
│   ├── db/                      # MongoDB client
│   ├── redis/                   # Redis client
│   ├── storage/                 # MinIO client
│   ├── queues/                  # BullMQ queues & semaphore
│   ├── repos/                   # Data repositories
│   ├── services/                # Business logic services
│   ├── schemas/                 # Zod schemas
│   ├── state/                   # Run state machine
│   ├── http/                    # HTTP utilities & errors
│   ├── logging/                 # Pino logger
│   └── utils/                   # Utilities
│
├── scripts/                      # Utility scripts
│   ├── seed-db.ts               # Database seeding
│   └── check-minio.ts           # MinIO connectivity check
│
├── tests/                        # Test setup
├── package.json
├── tsconfig.json
├── next.config.mjs
└── tailwind.config.ts
```

---

## 3. Pages & UI

### Routes

| Route | Page | Purpose |
|-------|------|---------|
| `/` | `app/page.tsx` | Hypothesis submission form with history |
| `/overview` | `app/overview/page.tsx` | Dashboard with run stats, activity, queues |
| `/ideation` | `app/ideation/page.tsx` | Ideation queue management |
| `/validations/queue` | `app/validations/queue/page.tsx` | Human validation queue |
| `/runs/[id]` | `app/runs/[id]/page.tsx` | Run detail with events, artifacts, progress |

### Key Components

| Component | Purpose |
|-----------|---------|
| `CreateHypothesisForm` | Form to submit new hypothesis |
| `HypothesisHistoryList` | Paginated hypothesis history |
| `RunTable` | Tabular list of runs with filtering/sorting |
| `RunDetailClient` | Full run detail page |
| `StageProgressPanel` | Visual stage progress breakdown |
| `StageTimingView` | Timing breakdown per stage |
| `PaperAnalysisPanel` | Quantitative/qualitative analysis display |
| `ArtifactList` | Run artifacts with download links |
| `PlotGallery` | Gallery of generated plots |
| `RunEventsFeed` | Timeline of run events |
| `LiveLogViewer` | Real-time log streaming |
| `HumanValidationForm` | Manual validation submission |
| `StatusBadge` | Run status indicator |

---

## 4. API Routes

### Event Ingestion

| Method | Route | Purpose |
|--------|-------|---------|
| `POST` | `/api/ingest/events` | Batch event ingestion (NDJSON) |
| `POST` | `/api/ingest/event` | Single event ingestion |

### Health

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/api/health` | Liveness probe |

### Runs

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/api/runs` | List runs with filtering |
| `GET` | `/api/runs/[id]` | Get single run |
| `POST` | `/api/runs/[id]/cancel` | Cancel a run |
| `GET` | `/api/runs/[id]/artifacts` | List run artifacts |
| `POST` | `/api/runs/[id]/artifacts/presign` | Generate presigned URLs |
| `GET` | `/api/runs/[id]/events` | Stream run events |
| `POST` | `/api/runs/[id]/analysis` | Trigger paper analysis |
| `POST` | `/api/runs/[id]/retry-writeup` | Retry paper generation |
| `POST` | `/api/runs/[id]/hide` | Hide run from UI |

### Hypotheses

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/api/hypotheses` | List hypotheses (paginated) |
| `POST` | `/api/hypotheses` | Create hypothesis and enqueue run |
| `GET` | `/api/hypotheses/[id]/runs` | Get runs for hypothesis |
| `POST` | `/api/hypotheses/[id]/hide` | Hide hypothesis |
| `POST` | `/api/hypotheses/extract-chatgpt` | Extract from ChatGPT URL |
| `POST` | `/api/hypotheses/extract-and-create` | Extract and auto-create |

### Ideations

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/api/ideations` | List ideation requests |
| `GET` | `/api/ideations/summary` | Queue status summary |

### Validations

| Method | Route | Purpose |
|--------|-------|---------|
| `POST` | `/api/validations/[runId]/human` | Submit human validation |

### Artifacts

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/api/artifacts/[...key]` | Download artifact from MinIO |

### Overview

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/api/overview` | System overview stats |

---

## 5. Services Layer

Location: `lib/services/`

### Events Service (`events.service.ts`)

Processes CloudEvents and routes to specific handlers.

```typescript
processEvent(event: CloudEvent): Promise<void>
handleEventByType(event: CloudEvent): Promise<void>
```

**Event Types Handled:**
- Run lifecycle: `ai.run.started`, `ai.run.completed`, `ai.run.failed`, `ai.run.canceled`
- Stage events: `ai.run.stage_started`, `ai.run.stage_progress`, `ai.run.stage_completed`
- Node events: `ai.node.created`, `ai.node.completed`, `ai.node.selected_best`
- Output events: `ai.paper.started`, `ai.paper.generated`, `ai.artifact.registered`
- Validation: `ai.validation.auto_started`, `ai.validation.auto_completed`

### Runs Service (`runs.service.ts`)

Manages run lifecycle and state transitions.

```typescript
enqueueRun(hypothesisId: string): Promise<Run>
transitionRun(runId: string, targetStatus: RunStatus, patch?: Partial<Run>): Promise<Run>
```

### RunPods Service (`runpods.service.ts`)

Manages RunPod GPU provisioning.

```typescript
createWorkerPod(options: CreatePodOptions): Promise<Pod>
waitForPodReady(podId: string, pollInterval: number, maxAttempts: number): Promise<Pod>
terminatePod(podId: string): Promise<void>
extractSSHInfo(pod: Pod, podHostId: string): SSHInfo
```

**CreatePodOptions:**
- `repoName`, `repoOrg`, `repoBranch` - Git repository
- `gpuTypes` - GPU list for round-robin fallback
- `gpuCount`, `containerDiskInGb`, `volumeInGb`
- `imageName` - Docker image
- `setupScripts`, `startupCommand`
- `autoTerminate`

### Analysis Service (`analysis.service.ts`)

Generates paper analysis using LLM.

```typescript
generatePaperAnalysis(input: AnalysisInput, llm?: OpenAI): Promise<PaperAnalysis>
```

### Ideation Service (`ideation.service.ts`)

Generates structured idea JSON from hypothesis.

```typescript
generateIdeaJson(title: string, idea: string): Promise<IdeaJson>
```

### Artifacts Service (`artifacts.service.ts`)

Manages artifact storage paths.

```typescript
buildArtifactPath(runId: string, key: string): string
```

### Deduplication Service (`deduplication.service.ts`)

Prevents duplicate event processing.

```typescript
isEventSeen(eventId: string): Promise<boolean>
markEventSeen(eventId: string, runId: string): Promise<void>
```

---

## 6. Data Layer

### Repositories (`lib/repos/`)

| Repository | Purpose |
|------------|---------|
| `runs.repo.ts` | Run CRUD, filtering, aggregations |
| `hypotheses.repo.ts` | Hypothesis CRUD |
| `events.repo.ts` | Event storage |
| `stages.repo.ts` | Stage tracking |
| `validations.repo.ts` | Validation records |
| `artifacts.repo.ts` | Artifact metadata |
| `ideations.repo.ts` | Ideation requests |
| `paperAnalyses.repo.ts` | Analysis results |

### MongoDB Collections

| Collection | Key Fields |
|------------|------------|
| `runs` | `_id`, `hypothesisId`, `status`, `pod`, `currentStage`, `stageTiming`, `metrics` |
| `hypotheses` | `_id`, `title`, `idea`, `createdBy`, `ideaJson`, `ideation` |
| `events` | `_id`, `runId`, `type`, `data`, `source`, `timestamp`, `seq` |
| `stages` | `_id`, `runId`, `name`, `status`, `progress`, `startedAt`, `completedAt` |
| `validations` | `_id`, `runId`, `kind`, `verdict`, `rubric`, `notes` |
| `artifacts` | `_id`, `runId`, `key`, `bytes`, `contentType`, `kind` |
| `ideations` | `_id`, `hypothesisId`, `status`, `reflections` |
| `paperAnalyses` | `_id`, `runId`, `quantitative`, `qualitative` |

### Redis Usage

- **Event Deduplication**: Event IDs with TTL
- **Job Queues**: `orchestrator`, `validator` (via BullMQ)
- **GPU Semaphore**: `gpu_slots` key for limiting concurrent pods

### MinIO Object Storage

- **Bucket**: `ai-scientist-artifacts` (configurable)
- **Structure**: `runs/{runId}/{artifact_key}`
- **Operations**: Presigned GET/PUT URLs, public URL generation

---

## 7. Event Processing

### CloudEvents Envelope

```typescript
{
  specversion: "1.0",
  id: string,              // Unique event ID
  source: string,          // Event source
  type: string,            // e.g., "ai.run.started"
  subject: "run/{runId}",  // Target entity
  time: ISO8601,
  datacontenttype: "application/json",
  data: {...},             // Event-specific payload
  extensions: {
    seq?: number,          // Ordering sequence
    traceparent?: string   // Trace ID
  }
}
```

### Event Types

**Run Lifecycle:**
- `ai.run.enqueued` → Creates run in QUEUED status
- `ai.run.started` → Transitions to RUNNING
- `ai.run.completed` → Transitions to COMPLETED
- `ai.run.failed` → Transitions to FAILED
- `ai.run.canceled` → Transitions to CANCELED
- `ai.run.heartbeat` → Updates lastHeartbeat

**Stage Events:**
- `ai.run.stage_started` → Creates Stage record
- `ai.run.stage_progress` → Updates progress percentage
- `ai.run.stage_metric` → Records stage metrics
- `ai.run.stage_completed` → Marks stage complete

**Node Events:**
- `ai.node.created` → Records node in pipeline
- `ai.node.code_generated` → Logs code generation
- `ai.node.executing` → Marks node running
- `ai.node.completed` → Records execution results
- `ai.node.selected_best` → Marks best node

**Output Events:**
- `ai.paper.started` → Paper generation started
- `ai.paper.generated` → Paper artifact registered
- `ai.artifact.registered` → Artifact stored in MinIO

**Validation Events:**
- `ai.validation.auto_started` → Auto-validation initiated
- `ai.validation.auto_completed` → Auto-validation result

### Event Processing Pipeline

1. CloudEvents envelope validation
2. Event data schema validation
3. Deduplication check via Redis
4. Event stored in MongoDB
5. Type-specific handler invoked
6. Run state machine validation
7. `lastEventSeq` updated

---

## 8. Run State Machine

Location: `lib/state/runStateMachine.ts`

### States

```
QUEUED → SCHEDULED → STARTING → RUNNING → AUTO_VALIDATING → AWAITING_HUMAN → HUMAN_VALIDATED
                                    ↓                                              ↓
                                  FAILED ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
                                    ↓
                                 CANCELED
```

### Valid Transitions

| From | Allowed Targets |
|------|-----------------|
| `QUEUED` | `SCHEDULED`, `CANCELED` |
| `SCHEDULED` | `STARTING`, `RUNNING`, `FAILED`, `CANCELED` |
| `STARTING` | `RUNNING`, `FAILED`, `CANCELED` |
| `RUNNING` | `AUTO_VALIDATING`, `FAILED`, `CANCELED`, `COMPLETED` |
| `AUTO_VALIDATING` | `AWAITING_HUMAN`, `FAILED`, `CANCELED` |
| `AWAITING_HUMAN` | `HUMAN_VALIDATED`, `FAILED`, `CANCELED` |
| `COMPLETED` | `AUTO_VALIDATING`, `AWAITING_HUMAN`, `HUMAN_VALIDATED`, `FAILED`, `CANCELED` |
| `HUMAN_VALIDATED`, `FAILED`, `CANCELED` | Terminal (no transitions) |

### Stage Names

- `Stage_1` - Experiments (Baseline, Creative, Ablations)
- `Stage_2` - Plot Aggregation
- `Stage_3` - Paper Generation
- `Stage_4` - Auto-Validation

---

## 9. RunPod Integration

Location: `lib/services/runpods.service.ts`

### Key Methods

| Method | Purpose |
|--------|---------|
| `createWorkerPod(options)` | Create GPU pod with retry logic |
| `waitForPodReady(podId)` | Poll until pod is running |
| `getPod(podId)` | Get current pod status |
| `listPods()` | List all account pods |
| `terminatePod(podId)` | Delete pod |
| `extractSSHInfo(pod)` | Parse SSH connection details |

### Features

- **GPU Round-Robin**: Falls back to alternative GPU types on 500 errors
- **Setup Scripts**: Pre-repository setup scripts array
- **Auto-Termination**: Pods terminate after completion
- **SSH Access**: Extracts connection info for debugging

### Pod Configuration

```typescript
{
  repoName: "AE-Scientist",
  repoOrg: "agencyenterprise",
  repoBranch: "main",
  gpuTypes: ["NVIDIA RTX A4000", "NVIDIA RTX A5000"],
  gpuCount: 1,
  containerDiskInGb: 30,
  volumeInGb: 50,
  imageName: "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404",
  autoTerminate: true
}
```

---

## 10. Queuing System

Location: `lib/queues/`

### BullMQ Queues

| Queue | Purpose |
|-------|---------|
| `orchestrator` | Run orchestration jobs |
| `validator` | Validation tasks |

### Job Configuration

```typescript
queue.add("start", { runId }, {
  attempts: 5,
  backoff: { type: "exponential", delay: 3000 },
  removeOnComplete: true
})
```

### GPU Semaphore

- **Key**: `POD_SEMAPHORE_KEY` env var
- **Max Slots**: `MAX_POD_SLOTS` (default: 4)
- **Lock Timeout**: 5 minutes
- **Acquire Timeout**: 30 seconds

---

## 11. Configuration

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `NODE_ENV` | No | Environment mode (default: "development") |
| `PORT` | No | HTTP port (default: 3000) |
| `MONGODB_URI` | Yes | MongoDB connection string |
| `MONGODB_DB` | Yes | Database name |
| `REDIS_URL` | Yes | Redis connection URL |
| `MINIO_ENDPOINT` | Yes | MinIO hostname/IP |
| `MINIO_PORT` | No | MinIO port |
| `MINIO_USE_SSL` | No | Use HTTPS for MinIO |
| `MINIO_ACCESS_KEY` | Yes | MinIO access key |
| `MINIO_SECRET_KEY` | Yes | MinIO secret key |
| `MINIO_BUCKET` | Yes | Bucket name |
| `MINIO_REGION` | Yes | AWS region |
| `MINIO_PUBLIC_BASE_URL` | Yes | Public MinIO URL |
| `POD_SEMAPHORE_KEY` | No | Redis semaphore key (default: "gpu_slots") |
| `MAX_POD_SLOTS` | No | Max concurrent pods (default: 4) |
| `OPENAI_API_KEY` | No | OpenAI API key (for paper analysis) |
| `RUNPOD_API_KEY` | No | RunPod API key |

---

## 12. Development

### Scripts

```bash
npm run dev         # Start dev server (port 3000)
npm run build       # Production build
npm start           # Run production server
npm run lint        # ESLint
npm run typecheck   # TypeScript check
npm run test        # Vitest unit tests
npm run seed        # Seed database
npm run check:minio # Verify MinIO connectivity
```

### Logging

Uses Pino with singleton pattern:

```typescript
import { createLogger } from "@/lib/logging/logger"

const logger = createLogger({ module: "runs.service" })
logger.info({ runId }, "Run created")
```

### Error Handling

Custom `HttpError` class with helpers:

```typescript
import { createNotFound, createBadRequest } from "@/lib/http/errors"

throw createNotFound("Run not found")
throw createBadRequest("Invalid hypothesis ID")
```

---

## 13. Key Schemas

Location: `lib/schemas/`

### Run Schema

```typescript
{
  _id: UUID,
  hypothesisId: UUID,
  status: RunStatus,
  pod?: { id, instanceType, region },
  currentStage?: { name, progress, iteration, maxIterations },
  stageTiming?: { [stageName]: { elapsed_s, duration_s, startedAt, completedAt } },
  metrics?: Record<string, number>,
  nodeHistory?: Array<{ nodeId, iteration, isBuggy, metric, timestamp }>,
  createdAt: Date,
  updatedAt: Date,
  startedAt?: Date,
  completedAt?: Date,
  failedAt?: Date,
  lastHeartbeat?: Date,
  lastEventSeq?: number,
  errorType?: string,
  errorMessage?: string,
  hidden?: boolean
}
```

### Hypothesis Schema

```typescript
{
  _id: UUID,
  title: string,
  idea: string,
  createdBy: string,
  createdAt: Date,
  ideaJson?: Record<string, any>,
  chatGptUrl?: string,
  ideation?: {
    requestId: UUID,
    status: IdeationStatus,
    reflections: number,
    ideas?: Array<IdeaJson>
  },
  seed?: boolean,
  hidden?: boolean
}
```

### Paper Analysis Schema

```typescript
{
  _id: UUID,
  runId: UUID,
  quantitative: {
    quality: number,
    faithfulness: number,
    innovation: number,
    efficiency: number,
    successRate: number,
    reliability: number,
    reproducibility: number
  },
  qualitative: {
    tradeoffs: string,
    hypothesisProof: string,
    conclusion: string,
    novelty: string,
    recommendations: string
  },
  models: { quantitative: string, qualitative: string },
  createdAt: Date
}
```
