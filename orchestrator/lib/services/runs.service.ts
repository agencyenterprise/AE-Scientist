import { randomUUID } from "node:crypto"
import { createLogger } from "../logging/logger"
import { createRun, findRunById, updateRun } from "../repos/runs.repo"
import { assertTransition } from "../state/runStateMachine"
import { type Run } from "../schemas/run"
import { getOrchestratorQueue } from "../queues/bullmq"

const log = createLogger({ module: "runs.service" })

export async function enqueueRun(hypothesisId: string): Promise<Run> {
  const run: Run = {
    _id: randomUUID(),
    hypothesisId,
    status: "QUEUED",
    createdAt: new Date(),
    updatedAt: new Date()
  }
  await createRun(run)
  try {
    await getOrchestratorQueue().add(
      "start",
      { runId: run._id },
      {
        attempts: 5,
        backoff: { type: "exponential", delay: 3000 },
        removeOnComplete: true
      }
    )
  } catch (error) {
    log.warn({ error, runId: run._id }, "Failed to enqueue run; worker disabled?")
  }
  return run
}

export async function transitionRun(
  runId: string,
  targetStatus: Run["status"],
  patch: Partial<Run> = {}
): Promise<Run> {
  const current = await findRunById(runId)
  if (!current) {
    throw new Error("Run not found")
  }
  assertTransition(current.status, targetStatus)
  await updateRun(runId, { ...patch, status: targetStatus })
  const updated = await findRunById(runId)
  if (!updated) {
    throw new Error("Run missing after update")
  }
  return updated
}

export async function cancelRun(runId: string): Promise<Run> {
  return transitionRun(runId, "CANCELED")
}
