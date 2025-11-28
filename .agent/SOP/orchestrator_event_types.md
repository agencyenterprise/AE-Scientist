# SOP: Orchestrator Event Types (CloudEvents)

## Related Documentation
- [Orchestrator Architecture](../System/orchestrator_architecture.md)
- [Project Architecture](../System/project_architecture.md)

---

## Overview

This SOP covers adding new CloudEvents event types to the orchestrator. Use this procedure when you need to:
- Define new event types for worker-orchestrator communication
- Add event data schemas
- Implement event handlers
- Process new types of telemetry

---

## Prerequisites

- Understanding of CloudEvents specification
- Knowledge of the event's purpose and data structure
- Understanding of the state machine (if event affects run status)

---

## Step-by-Step Procedure

### 1. Define the Event Data Schema

Add the Zod schema to `orchestrator/lib/schemas/cloudevents.ts`:

```typescript
// orchestrator/lib/schemas/cloudevents.ts

// Define the event data schema
export const MyFeatureStartedDataZ = z.object({
  run_id: z.string().uuid(),
  feature_name: z.string(),
  config: z.record(z.any()).optional(),
  timestamp: z.string().datetime().optional()
})

export const MyFeatureCompletedDataZ = z.object({
  run_id: z.string().uuid(),
  feature_name: z.string(),
  result: z.enum(["success", "failure"]),
  metrics: z.object({
    duration_ms: z.number(),
    items_processed: z.number()
  }).optional(),
  error_message: z.string().optional()
})

export const MyFeatureProgressDataZ = z.object({
  run_id: z.string().uuid(),
  feature_name: z.string(),
  progress: z.number().min(0).max(1),
  current_step: z.string().optional(),
  total_steps: z.number().optional()
})
```

### 2. Register in EVENT_TYPE_DATA_SCHEMAS

Add the new event types to the schema map:

```typescript
// orchestrator/lib/schemas/cloudevents.ts

export const EVENT_TYPE_DATA_SCHEMAS = {
  // Existing events...
  "ai.run.started": RunStartedDataZ,
  "ai.run.completed": RunCompletedDataZ,

  // New events
  "ai.myfeature.started": MyFeatureStartedDataZ,
  "ai.myfeature.completed": MyFeatureCompletedDataZ,
  "ai.myfeature.progress": MyFeatureProgressDataZ,
} as const

export type EventType = keyof typeof EVENT_TYPE_DATA_SCHEMAS
```

### 3. Export Types

```typescript
// orchestrator/lib/schemas/cloudevents.ts

export type MyFeatureStartedData = z.infer<typeof MyFeatureStartedDataZ>
export type MyFeatureCompletedData = z.infer<typeof MyFeatureCompletedDataZ>
export type MyFeatureProgressData = z.infer<typeof MyFeatureProgressDataZ>
```

### 4. Implement Event Handlers

Add handlers in `orchestrator/lib/services/events.service.ts`:

```typescript
// orchestrator/lib/services/events.service.ts

import { createLogger } from "../logging/logger"
import { updateRun, findRunById } from "../repos/runs.repo"
import type {
  MyFeatureStartedData,
  MyFeatureCompletedData,
  MyFeatureProgressData
} from "../schemas/cloudevents"

const log = createLogger({ module: "events.service" })

// Handler for my feature started
async function handleMyFeatureStarted(
  runId: string,
  data: MyFeatureStartedData
): Promise<void> {
  log.info({ runId, featureName: data.feature_name }, "My feature started")

  await updateRun(runId, {
    currentFeature: {
      name: data.feature_name,
      status: "running",
      startedAt: new Date()
    },
    updatedAt: new Date()
  })
}

// Handler for my feature completed
async function handleMyFeatureCompleted(
  runId: string,
  data: MyFeatureCompletedData
): Promise<void> {
  log.info({
    runId,
    featureName: data.feature_name,
    result: data.result
  }, "My feature completed")

  const update: Partial<Run> = {
    currentFeature: {
      name: data.feature_name,
      status: data.result === "success" ? "completed" : "failed",
      completedAt: new Date()
    },
    updatedAt: new Date()
  }

  if (data.metrics) {
    update.metrics = {
      ...update.metrics,
      [`${data.feature_name}_duration_ms`]: data.metrics.duration_ms,
      [`${data.feature_name}_items`]: data.metrics.items_processed
    }
  }

  if (data.result === "failure" && data.error_message) {
    update.errorMessage = data.error_message
  }

  await updateRun(runId, update)
}

// Handler for my feature progress
async function handleMyFeatureProgress(
  runId: string,
  data: MyFeatureProgressData
): Promise<void> {
  log.debug({
    runId,
    featureName: data.feature_name,
    progress: data.progress
  }, "My feature progress")

  await updateRun(runId, {
    currentFeature: {
      name: data.feature_name,
      progress: data.progress,
      currentStep: data.current_step
    },
    updatedAt: new Date()
  })
}
```

### 5. Register Handlers in Event Router

Update the event routing in `events.service.ts`:

```typescript
// orchestrator/lib/services/events.service.ts

export async function handleEventByType(
  event: CloudEventsEnvelope,
  runId: string,
  eventSeq?: number
): Promise<void> {
  const { type, data } = event

  switch (type) {
    // Existing handlers...
    case "ai.run.started":
      await handleRunStarted(runId, data as RunStartedData)
      break

    case "ai.run.completed":
      await handleRunCompleted(runId, data as RunCompletedData)
      break

    // New handlers
    case "ai.myfeature.started":
      await handleMyFeatureStarted(runId, data as MyFeatureStartedData)
      break

    case "ai.myfeature.completed":
      await handleMyFeatureCompleted(runId, data as MyFeatureCompletedData)
      break

    case "ai.myfeature.progress":
      await handleMyFeatureProgress(runId, data as MyFeatureProgressData)
      break

    default:
      log.warn({ type }, "Unknown event type")
  }
}
```

---

## CloudEvents Envelope Structure

All events follow the CloudEvents v1.0 specification:

```typescript
interface CloudEventsEnvelope {
  specversion: "1.0"
  id: string                    // Unique event ID (UUID)
  source: string               // Event source identifier
  type: string                 // Event type (e.g., "ai.myfeature.started")
  subject: string              // Target entity (e.g., "run/{runId}")
  time: string                 // ISO8601 timestamp
  datacontenttype: "application/json"
  data: Record<string, unknown> // Event-specific payload
  extensions?: {
    seq?: number               // Event sequence for ordering
    traceparent?: string       // OpenTelemetry trace ID
  }
}
```

---

## Event Type Naming Convention

Follow the pattern: `ai.{domain}.{action}`

| Domain | Actions | Example |
|--------|---------|---------|
| `run` | started, completed, failed, canceled | `ai.run.started` |
| `stage` | started, progress, completed | `ai.run.stage_started` |
| `node` | created, executing, completed | `ai.node.completed` |
| `paper` | started, generated | `ai.paper.generated` |
| `artifact` | registered, failed | `ai.artifact.registered` |
| `validation` | auto_started, auto_completed | `ai.validation.auto_completed` |

---

## Key Files

| File | Purpose |
|------|---------|
| `lib/schemas/cloudevents.ts` | Event schemas and type registry |
| `lib/services/events.service.ts` | Event processing and handlers |
| `app/api/ingest/event/route.ts` | Event ingestion endpoint |
| `lib/repos/events.repo.ts` | Event storage |

---

## Event Processing Pipeline

1. **Ingestion** (`/api/ingest/event`)
   - Receive CloudEvents envelope
   - Validate envelope structure

2. **Validation** (`validateEventData`)
   - Look up schema in `EVENT_TYPE_DATA_SCHEMAS`
   - Validate event data against schema

3. **Deduplication** (`isEventSeen`)
   - Check Redis for duplicate event ID
   - Skip if already processed

4. **Storage** (`createEvent`)
   - Store event in MongoDB `events` collection

5. **Processing** (`handleEventByType`)
   - Route to type-specific handler
   - Update run state, metrics, etc.

6. **Sequence Tracking** (`updateRun`)
   - Update `lastEventSeq` on run document

---

## Common Patterns

### Progress Events

```typescript
export const ProgressDataZ = z.object({
  run_id: z.string().uuid(),
  progress: z.number().min(0).max(1),  // 0.0 to 1.0
  iteration: z.number().optional(),
  max_iterations: z.number().optional(),
  current_step: z.string().optional()
})
```

### Metric Events

```typescript
export const MetricDataZ = z.object({
  run_id: z.string().uuid(),
  metric_name: z.string(),
  value: z.number(),
  unit: z.string().optional(),
  tags: z.record(z.string()).optional()
})
```

### Error Events

```typescript
export const ErrorDataZ = z.object({
  run_id: z.string().uuid(),
  error_type: z.string(),
  error_message: z.string(),
  traceback: z.string().optional(),
  context: z.record(z.any()).optional()
})
```

---

## Testing Event Handling

Send a test event via curl:

```bash
curl -X POST http://localhost:3000/api/ingest/event \
  -H "Content-Type: application/json" \
  -d '{
    "specversion": "1.0",
    "id": "test-event-001",
    "source": "test",
    "type": "ai.myfeature.started",
    "subject": "run/your-run-uuid",
    "time": "2024-01-01T00:00:00Z",
    "datacontenttype": "application/json",
    "data": {
      "run_id": "your-run-uuid",
      "feature_name": "test_feature"
    }
  }'
```

---

## Common Pitfalls

- **Always add schema to EVENT_TYPE_DATA_SCHEMAS**: Otherwise validation fails
- **Use consistent naming**: Follow `ai.{domain}.{action}` pattern
- **Include run_id in data**: Needed for correlation
- **Handle unknown events gracefully**: Log warning, don't throw
- **Update sequence tracking**: Prevents out-of-order processing
- **Export types**: Make types available for consumers

---

## Verification

1. Add schema and check TypeScript compiles:
   ```bash
   npm run typecheck
   ```

2. Test validation:
   ```typescript
   import { validateEventData } from "@/lib/schemas/cloudevents"

   const isValid = validateEventData("ai.myfeature.started", {
     run_id: "uuid",
     feature_name: "test"
   })
   ```

3. Send test event and check logs

4. Verify run document updated in MongoDB:
   ```bash
   mongosh --eval "db.runs.findOne({_id: 'your-run-uuid'})"
   ```

5. Check event stored in events collection:
   ```bash
   mongosh --eval "db.events.find({type: 'ai.myfeature.started'})"
   ```
