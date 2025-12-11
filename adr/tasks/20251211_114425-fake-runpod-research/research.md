# 🔍 Feature Area: Fake RunPod Server

## Summary

The fake RunPod server is a FastAPI-based development tool that simulates RunPod's GPU cloud APIs for local testing. It creates a `FakeRunner` thread on pod creation that emits realistic telemetry events (stage progress, logs, artifacts) over a ~5-minute timeline without requiring actual GPU infrastructure.

## Code Paths Found

| File                                                          | Lines            | Purpose                                                            | Action    |
| ------------------------------------------------------------- | ---------------- | ------------------------------------------------------------------ | --------- |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 65-594           | Complete fake server implementation                                | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 65               | FastAPI app definition                                             | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 66-68            | In-memory pod registry and telemetry storage                       | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 141-189          | POST /pods endpoint - creates pod, spawns FakeRunner               | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 192-198          | GET /pods/{pod_id} - returns pod status                            | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 201-205          | DELETE /pods/{pod_id} - removes pod                                | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 208-224          | GET /billing/pods - returns mock $0.00 billing                     | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 227-233          | POST /graphql - returns fake podHostId                             | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 236-298          | Telemetry endpoints (run-started, heartbeat, stage-progress, etc.) | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 313-579          | FakeRunner class - simulates full pipeline execution               | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 336-341          | Stage plan: 4 stages × 3 iterations                                | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 361-375          | run() - main execution flow                                        | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 390-445          | \_emit_progress_flow() - stages 1-4 iteration loop                 | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 450-531          | \_emit_paper_generation_flow() - stage 5 paper steps               | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 533-561          | \_publish_fake_artifact() - uploads to real S3                     | reference |
| `server/app/services/research_pipeline/fake_runpod_server.py` | 581-593          | main() - starts uvicorn server on FAKE_RUNPOD_PORT                 | reference |
| `server/app/services/research_pipeline/runpod_manager.py`     | 28-34            | RunPodManager init checks for FAKE_RUNPOD_BASE_URL override        | reference |
| `server/env.example`                                          | 55-56            | Environment variable examples for fake server                      | reference |
| `server/README.md`                                            | 325-327, 395-397 | Usage documentation for fake server                                | reference |
| `.agent/System/fake_runpod_server.md`                         | 1-353            | Comprehensive documentation of fake server                         | reference |

## Key Patterns

### FastAPI Service Pattern

```python
# server/app/services/research_pipeline/fake_runpod_server.py:65
app = FastAPI(title="Fake RunPod Server")
_pods: Dict[str, PodRecord] = {}
_lock = threading.Lock()
```

- In-memory state with thread locks
- RESTful endpoints + GraphQL endpoint
- FastAPI standard router pattern

### Background Thread Pattern

```python
# fake_runpod_server.py:111-112, 137-138
thread = threading.Thread(target=_transition, name=f"fake-ready-{record.id}", daemon=True)
thread.start()
```

- Daemon threads for pod state transitions and runner execution
- Thread-per-runner model

### Event Persistence Pattern

```python
# fake_runpod_server.py:349-357
self._persistence = EventPersistenceManager(
    database_url=self._database_url,
    run_id=self._run_id,
    webhook_client=webhook_client,
)
# Falls back to LocalPersistence if DB unavailable
```

- Shared `EventPersistenceManager` from research_pipeline
- Queue-based event publishing
- Webhook + DB dual persistence

## Integration Points

### 1. RunPodManager URL Override

```python
# runpod_manager.py:31-34
base_url_override = os.environ.get("FAKE_RUNPOD_BASE_URL")
graphql_url_override = os.environ.get("FAKE_RUNPOD_GRAPHQL_URL")
self.base_url = base_url_override or "https://rest.runpod.io/v1"
self.graphql_url = graphql_url_override or "https://api.runpod.io/graphql"
```

**Flow**: Set `FAKE_RUNPOD_BASE_URL=http://127.0.0.1:9000` → RunPodManager uses fake server

### 2. Pod Creation Flow

```
Client → RunPodManager.create_pod() → POST /pods → FakeRunner.start()
                                                    ↓
                                          EventPersistenceManager
                                                    ↓
                                          PostgreSQL + WebhookClient
                                                    ↓
                                          Server Webhooks → SSE → Frontend
```

### 3. Event Types Emitted

- **run_started**: fake_runpod_server.py:563-568
- **run_stage_progress**: fake_runpod_server.py:398-414 (stages 1-4)
- **paper_generation_progress**: fake_runpod_server.py:494-509 (stage 5)
- **run_log**: fake_runpod_server.py:415-423
- **substage_completed**: fake_runpod_server.py:433-445
- **heartbeat**: fake_runpod_server.py:377-388 (every 10s)
- **run_finished**: fake_runpod_server.py:570-578

### 4. Artifact Publishing

```python
# fake_runpod_server.py:533-561
ArtifactPublisher(
    run_id=self._run_id,
    aws_access_key_id=...,
    aws_secret_access_key=...,
).publish(spec=ArtifactSpec(artifact_type="fake_result", path=artifact_path))
```

**Note**: Uploads to REAL S3 bucket despite being "fake"

## Constraints Discovered

### Environment Requirements

**Required at runtime** (fake_runpod_server.py:71-75, 176-178):

- `FAKE_RUNPOD_PORT` - Server listen port (default: 9000)
- `TELEMETRY_WEBHOOK_URL` - Webhook destination for events
- `TELEMETRY_WEBHOOK_TOKEN` - Auth token for webhooks
- `DATABASE_PUBLIC_URL` - PostgreSQL connection for event persistence

**Required in pod env** (fake_runpod_server.py:145-158):

- `RUN_ID` - Research run identifier
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_S3_BUCKET_NAME` - For artifact uploads

### Timing Constraints

- Pod transitions to RUNNING after 1 second (fake_runpod_server.py:175)
- Stage iterations: 20 seconds each (fake_runpod_server.py:424)
- Paper generation substeps: 5 seconds each (fake_runpod_server.py:520)
- Heartbeat interval: 10 seconds (fake_runpod_server.py:342)
- **Total simulation time**: ~5 minutes

### Concurrency Model

- Thread-safe pod registry via `_lock` (fake_runpod_server.py:67, 93-109, 173-174)
- One daemon thread per pod for state transitions (fake_runpod_server.py:111-112)
- One daemon thread per runner (fake_runpod_server.py:137-138)
- One daemon thread per runner for heartbeats (fake_runpod_server.py:364-366)

### Stage Simulation

**Hardcoded stage plan** (fake_runpod_server.py:336-341):

1. `1_initial_implementation_1_preliminary` - 3 of 10 iterations
2. `2_baseline_tuning_1_first_attempt` - 3 of 5 iterations
3. `3_creative_research_1_first_attempt` - 3 of 5 iterations
4. `4_ablation_studies_1_first_attempt` - 3 of 5 iterations

**Paper generation steps** (fake_runpod_server.py:453-486):

- plot_aggregation (3 substeps)
- citation_gathering (3 substeps)
- paper_writeup (6 substeps)
- paper_review (3 substeps)

### Limitations

1. **No actual ML execution** - purely simulated progress
2. **Fixed timing** - cannot be dynamically adjusted
3. **In-memory state** - pod registry lost on restart
4. **Real AWS required** - artifact uploads go to actual S3
5. **No error injection** - always succeeds (success=True)

## Usage Pattern

### Start Fake Server

```bash
# From server/ directory
make fake-runpod

# Or manually
VIRTUAL_ENV= PYTHONPATH=../research_pipeline:..:$(PYTHONPATH) \
  uv run python -m app.services.research_pipeline.fake_runpod_server
```

### Configure RunPodManager

```bash
export FAKE_RUNPOD_BASE_URL="http://127.0.0.1:9000"
export FAKE_RUNPOD_GRAPHQL_URL="http://127.0.0.1:9000/graphql"
```

### Expected Behavior

1. Pod creation returns immediately with `id="fake-{uuid}"`
2. Pod transitions to RUNNING after 1s
3. FakeRunner emits events for ~5 minutes
4. Artifact uploaded to S3
5. Run finishes with success=True
