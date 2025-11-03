import { z } from "zod"
import { STAGES } from "../state/constants"

export const CloudEventsEnvelopeZ = z.object({
  specversion: z.literal("1.0"),
  id: z.string().min(1),
  source: z.string().min(1),
  type: z.string().min(1),
  subject: z.string().min(1),
  time: z.string().datetime(),
  datacontenttype: z.literal("application/json"),
  data: z.record(z.any()),
  extensions: z
    .object({
      seq: z.number().int().positive().optional(),
      traceparent: z.string().optional()
    })
    .optional()
})

export type CloudEventsEnvelope = z.infer<typeof CloudEventsEnvelopeZ>

export const RunStartedDataZ = z.object({
  run_id: z.string(),
  pod_id: z.string(),
  gpu: z.string().optional(),
  region: z.string().optional(),
  image: z.string().optional()
})

export const RunHeartbeatDataZ = z.object({
  run_id: z.string(),
  gpu_util: z.number().optional(),
  mem_gb: z.number().optional(),
  temp_c: z.number().optional()
})

export const RunStatusChangedDataZ = z.object({
  run_id: z.string(),
  from: z.string(),
  to: z.string(),
  reason: z.string().optional()
})

export const RunFailedDataZ = z.object({
  run_id: z.string(),
  stage: z.string().optional(),
  code: z.string(),
  message: z.string(),
  traceback: z.string().optional(),
  retryable: z.boolean().optional()
})

export const RunCanceledDataZ = z.object({
  run_id: z.string(),
  by: z.string().optional(),
  reason: z.string().optional()
})

export const StageStartedDataZ = z.object({
  run_id: z.string(),
  stage: z.enum(STAGES),
  desc: z.string().nullable().optional()
})

export const StageProgressDataZ = z.preprocess(
  (val: any) => {
    // Defensive: Clamp progress to [0, 1] to prevent crashes from backend bugs
    if (val && typeof val === 'object' && typeof val.progress === 'number') {
      return {
        ...val,
        progress: Math.max(0, Math.min(val.progress, 1))
      }
    }
    return val
  },
  z.object({
    run_id: z.string(),
    stage: z.enum(STAGES),
    progress: z.number().min(0).max(1),
    eta_s: z.number().nullable().optional(),
    iteration: z.number().int().optional(),
    max_iterations: z.number().int().optional(),
    good_nodes: z.number().int().optional(),
    buggy_nodes: z.number().int().optional(),
    total_nodes: z.number().int().optional(),
    best_metric: z.string().nullable().optional()
  })
)

export const StageMetricDataZ = z.object({
  run_id: z.string(),
  stage: z.enum(STAGES),
  name: z.string(),
  value: z.number()
})

export const StageCompletedDataZ = z.object({
  run_id: z.string(),
  stage: z.enum(STAGES),
  duration_s: z.number().nullable().optional(),
  summary: z.record(z.any()).nullable().optional()
})

export const IdeationGeneratedDataZ = z.object({
  run_id: z.string(),
  count: z.number().int(),
  top_k: z.array(z.string()).nullable().optional()
})

export const PaperGeneratedDataZ = z.object({
  run_id: z.string(),
  artifact_key: z.string(),
  word_count: z.number().int().nullable().optional()
})

export const ValidationAutoStartedDataZ = z.object({
  run_id: z.string(),
  model: z.string(),
  rubric_version: z.string().nullable().optional()
})

export const ValidationAutoCompletedDataZ = z.object({
  run_id: z.string(),
  verdict: z.enum(["pass", "fail"]),
  scores: z.record(z.number()).nullable().optional(),
  notes: z.string().nullable().optional()
})

export const RunLogDataZ = z.object({
  run_id: z.string(),
  level: z.enum(["debug", "info", "warn", "error"]),
  message: z.string(),
  kv: z.record(z.any()).nullable().optional(),
  source: z.string().nullable().optional()
})

export const ArtifactRegisteredDataZ = z.object({
  run_id: z.string(),
  key: z.string(),
  bytes: z.number().int(),
  sha256: z.string().nullable().optional(),
  content_type: z.string(),
  kind: z.string()
})

export const ArtifactFailedDataZ = z.object({
  run_id: z.string(),
  key: z.string(),
  code: z.string(),
  message: z.string()
})

export const ArtifactDetectedDataZ = z.object({
  run_id: z.string(),
  path: z.string(),
  type: z.string(),
  size_bytes: z.number().int()
})

export const NodeCreatedDataZ = z.object({
  run_id: z.string(),
  stage: z.enum(STAGES),
  node_id: z.string(),
  parent_id: z.string().nullable().optional()
})

export const NodeCodeGeneratedDataZ = z.object({
  run_id: z.string(),
  stage: z.enum(STAGES),
  node_id: z.string(),
  code_size_bytes: z.number().int()
})

export const NodeExecutingDataZ = z.object({
  run_id: z.string(),
  stage: z.enum(STAGES),
  node_id: z.string()
})

export const NodeCompletedDataZ = z.object({
  run_id: z.string(),
  stage: z.enum(STAGES),
  node_id: z.string(),
  is_buggy: z.boolean(),
  metric: z.string().nullable().optional(),
  exec_time_s: z.number()
})

export const NodeSelectedBestDataZ = z.object({
  run_id: z.string(),
  stage: z.enum(STAGES),
  node_id: z.string(),
  metric: z.string()
})

export const RunCompletedDataZ = z.object({
  run_id: z.string(),
  total_duration_s: z.number().int()
})

export const PaperStartedDataZ = z.object({
  run_id: z.string()
})

export const EVENT_TYPE_DATA_SCHEMAS = {
  "ai.run.enqueued": z.object({ run_id: z.string(), hypothesis_id: z.string(), priority: z.string().optional() }),
  "ai.run.started": RunStartedDataZ,
  "ai.run.heartbeat": RunHeartbeatDataZ,
  "ai.run.status_changed": RunStatusChangedDataZ,
  "ai.run.completed": RunCompletedDataZ,
  "ai.run.failed": RunFailedDataZ,
  "ai.run.canceled": RunCanceledDataZ,
  "ai.run.stage_started": StageStartedDataZ,
  "ai.run.stage_progress": StageProgressDataZ,
  "ai.run.stage_metric": StageMetricDataZ,
  "ai.run.stage_completed": StageCompletedDataZ,
  "ai.node.created": NodeCreatedDataZ,
  "ai.node.code_generated": NodeCodeGeneratedDataZ,
  "ai.node.executing": NodeExecutingDataZ,
  "ai.node.completed": NodeCompletedDataZ,
  "ai.node.selected_best": NodeSelectedBestDataZ,
  "ai.ideation.generated": IdeationGeneratedDataZ,
  "ai.paper.started": PaperStartedDataZ,
  "ai.paper.generated": PaperGeneratedDataZ,
  "ai.validation.auto_started": ValidationAutoStartedDataZ,
  "ai.validation.auto_completed": ValidationAutoCompletedDataZ,
  "ai.run.log": RunLogDataZ,
  "ai.artifact.detected": ArtifactDetectedDataZ,
  "ai.artifact.registered": ArtifactRegisteredDataZ,
  "ai.artifact.failed": ArtifactFailedDataZ
} as const

export type EventType = keyof typeof EVENT_TYPE_DATA_SCHEMAS

export function validateEventData(type: string, data: unknown): boolean {
  const schema = EVENT_TYPE_DATA_SCHEMAS[type as EventType]
  if (!schema) {
    return false
  }
  const result = schema.safeParse(data)
  return result.success
}

export function validateEventDataWithDetails(type: string, data: unknown): { 
  success: boolean
  errors?: Array<{ path: string; message: string; received?: any }>
} {
  const schema = EVENT_TYPE_DATA_SCHEMAS[type as EventType]
  if (!schema) {
    return { 
      success: false, 
      errors: [{ path: 'type', message: `Unknown event type: ${type}` }]
    }
  }
  const result = schema.safeParse(data)
  if (result.success) {
    return { success: true }
  }
  return {
    success: false,
    errors: result.error.errors.map(err => ({
      path: err.path.join('.') || 'root',
      message: err.message,
      received: (err as any).received
    }))
  }
}

