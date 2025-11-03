import { getDb } from "../db/mongo"
import { updateRun, findRunById } from "../repos/runs.repo"
import { createStage, updateStage } from "../repos/stages.repo"
import { createValidation } from "../repos/validations.repo"
import { createArtifact } from "../repos/artifacts.repo"
import { createEvent } from "../repos/events.repo"
import { assertTransition } from "../state/runStateMachine"
import { type CloudEventsEnvelope } from "../schemas/cloudevents"
import { type RunStatus } from "../state/constants"
import { logger } from "../logging/logger"

export async function processEvent(event: CloudEventsEnvelope): Promise<void> {
  const runId = event.subject.replace("run/", "")
  const eventSeq = event.extensions?.seq

  logger.info({ 
    eventType: event.type, 
    runId: runId.slice(0, 8),
    seq: eventSeq 
  }, "Processing event")

  if (eventSeq !== undefined) {
    const run = await findRunById(runId)
    if (!run) {
      logger.warn({ runId, eventId: event.id }, "Run not found for event")
      return
    }

    const lastSeq = run.lastEventSeq ?? 0
    if (eventSeq <= lastSeq) {
      logger.info({ runId, eventSeq, lastSeq }, "Ignoring out-of-order or duplicate event")
      return
    }
  }

  const eventDoc: any = {
    _id: event.id,
    runId,
    type: event.type,
    data: event.data,
    source: event.source,
    timestamp: new Date(event.time),
    seq: eventSeq
  }
  
  // Only add message and level for log events
  if (event.type === "ai.run.log") {
    if (event.data.message) {
      eventDoc.message = event.data.message
    }
    if (event.data.level) {
      eventDoc.level = event.data.level
    }
  }
  
  await createEvent(eventDoc)

  try {
    await handleEventByType(event, runId, eventSeq)
    logger.info({ eventType: event.type, runId: runId.slice(0, 8) }, "Event handled successfully")
  } catch (error) {
    logger.error({ eventType: event.type, runId, error }, "Error handling event")
    throw error
  }

  if (eventSeq !== undefined) {
    await updateRun(runId, { lastEventSeq: eventSeq })
  }
}

async function handleEventByType(
  event: CloudEventsEnvelope,
  runId: string,
  eventSeq: number | undefined
): Promise<void> {
  switch (event.type) {
    case "ai.run.started":
      await handleRunStarted(runId, event, eventSeq)
      break
    case "ai.run.heartbeat":
      await handleRunHeartbeat(runId, event, eventSeq)
      break
    case "ai.run.completed":
      await handleRunCompleted(runId, event, eventSeq)
      break
    case "ai.run.failed":
      await handleRunFailed(runId, event, eventSeq)
      break
    case "ai.run.canceled":
      await handleRunCanceled(runId, event, eventSeq)
      break
    case "ai.run.stage_started":
      await handleStageStarted(runId, event, eventSeq)
      break
    case "ai.run.stage_progress":
      await handleStageProgress(runId, event, eventSeq)
      break
    case "ai.run.stage_metric":
      await handleStageMetric(runId, event, eventSeq)
      break
    case "ai.run.stage_completed":
      await handleStageCompleted(runId, event, eventSeq)
      break
    case "ai.validation.auto_started":
      await handleValidationAutoStarted(runId, event, eventSeq)
      break
    case "ai.validation.auto_completed":
      await handleValidationAutoCompleted(runId, event, eventSeq)
      break
    case "ai.artifact.registered":
      await handleArtifactRegistered(runId, event, eventSeq)
      break
    case "ai.run.log":
      break
    default:
      logger.warn({ type: event.type }, "Unknown event type - no handler")
  }
}

async function handleRunStarted(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  const data = event.data
  await transitionRunStatus(runId, "RUNNING", eventSeq)
  await updateRun(runId, {
    pod: {
      id: data.pod_id,
      instanceType: data.gpu,
      region: data.region
    },
    startedAt: new Date(event.time),
    lastHeartbeat: new Date(event.time),
    errorType: null,
    errorMessage: null,
    errorTraceback: null
  })
}

async function handleRunHeartbeat(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  await updateRun(runId, {
    lastHeartbeat: new Date(event.time)
  })
}

async function handleRunCompleted(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  await transitionRunStatus(runId, "COMPLETED", eventSeq)
  await updateRun(runId, {
    completedAt: new Date(event.time)
  })
}

async function handleRunFailed(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  const data = event.data
  await transitionRunStatus(runId, "FAILED", eventSeq)
  await updateRun(runId, {
    failedAt: new Date(event.time),
    errorType: data.code,
    errorMessage: data.message,
    errorTraceback: data.traceback ?? null
  })
}

async function handleRunCanceled(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  await transitionRunStatus(runId, "CANCELED", eventSeq)
}

async function handleStageStarted(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  const data = event.data
  const canonicalStages = ["Stage_1", "Stage_2", "Stage_3", "Stage_4"]
  
  // Normalize stage name (backend might send "Stage 1: ..." or "Stage_1")
  let stageName = data.stage
  if (!canonicalStages.includes(stageName)) {
    // Try to extract stage number from display name
    const match = stageName.match(/Stage\s*(\d+)/)
    if (match) {
      stageName = `Stage_${match[1]}`
    }
  }
  
  const stageIndex = canonicalStages.indexOf(stageName)
  const { randomUUID } = await import("node:crypto")
  
  await createStage({
    _id: randomUUID(),
    runId,
    index: stageIndex,
    name: stageName,
    status: "RUNNING",
    startedAt: new Date(event.time),
    progress: 0
  })
  await updateRun(runId, {
    currentStage: {
      name: stageName,
      progress: 0
    }
  })
}

async function handleStageProgress(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  const data = event.data
  const canonicalStages = ["Stage_1", "Stage_2", "Stage_3", "Stage_4"]
  
  // Normalize stage name
  let stageName = data.stage
  if (!canonicalStages.includes(stageName)) {
    const match = stageName.match(/Stage\s*(\d+)/)
    if (match) {
      stageName = `Stage_${match[1]}`
    }
  }
  
  // Find stage by runId and name instead of composite _id
  const db = await import("../db/mongo").then(m => m.getDb())
  await db.collection("stages").updateOne(
    { runId, name: stageName },
    { $set: { progress: data.progress, updatedAt: new Date(event.time) } }
  )
  
  const updateData: any = {
    currentStage: {
      name: stageName,
      progress: data.progress,
      iteration: data.iteration,
      maxIterations: data.max_iterations,
      goodNodes: data.good_nodes,
      buggyNodes: data.buggy_nodes,
      totalNodes: data.total_nodes,
      bestMetric: data.best_metric
    },
    updatedAt: new Date(event.time)
  }
  
  await updateRun(runId, updateData)
}

async function handleStageMetric(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  const data = event.data
  const run = await findRunById(runId)
  if (!run) return

  const metrics = { ...(run.metrics || {}), [data.name]: data.value }
  await updateRun(runId, { metrics })
}

async function handleStageCompleted(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  const data = event.data
  const canonicalStages = ["Stage_1", "Stage_2", "Stage_3", "Stage_4"]
  
  // Normalize stage name
  let stageName = data.stage
  if (!canonicalStages.includes(stageName)) {
    const match = stageName.match(/Stage\s*(\d+)/)
    if (match) {
      stageName = `Stage_${match[1]}`
    }
  }
  
  const db = await import("../db/mongo").then(m => m.getDb())
  await db.collection("stages").updateOne(
    { runId, name: stageName },
    { $set: { status: "COMPLETED", completedAt: new Date(event.time), progress: 1 } }
  )
  
  const run = await findRunById(runId)
  if (run && run.stageTiming) {
    await updateRun(runId, {
      [`stageTiming.${stageName}.duration_s`]: data.duration_s,
      [`stageTiming.${stageName}.completedAt`]: new Date(event.time)
    })
  }
}

async function handleValidationAutoStarted(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  await transitionRunStatus(runId, "AUTO_VALIDATING", eventSeq)
}

async function handleValidationAutoCompleted(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  const data = event.data
  const { randomUUID } = await import("node:crypto")
  
  await createValidation({
    _id: randomUUID(),
    runId,
    kind: "auto",
    verdict: data.verdict as "pass" | "fail",
    rubric: data.scores as Record<string, number> | undefined,
    notes: data.notes || "",
    createdAt: new Date(event.time),
    createdBy: "auto"
  })

  await transitionRunStatus(runId, "AWAITING_HUMAN", eventSeq)
}

async function handleArtifactRegistered(
  runId: string,
  event: CloudEventsEnvelope,
  eventSeq: number | undefined
): Promise<void> {
  const data = event.data
  const { randomUUID } = await import("node:crypto")
  
  await createArtifact({
    _id: randomUUID(),
    runId,
    key: data.key,
    uri: data.key,
    contentType: data.content_type,
    size: data.bytes,
    createdAt: new Date(event.time)
  })
}

async function transitionRunStatus(
  runId: string,
  newStatus: RunStatus,
  eventSeq: number | undefined
): Promise<void> {
  const run = await findRunById(runId)
  if (!run) {
    throw new Error(`Run ${runId} not found`)
  }

  if (run.status === newStatus) {
    return
  }

  try {
    assertTransition(run.status, newStatus)
  } catch (error) {
    logger.warn(
      { runId, from: run.status, to: newStatus, error },
      "Skipping illegal state transition"
    )
    return
  }

  await updateRun(runId, { status: newStatus })
}
