import { Queue } from "bullmq"
import { getEnv } from "../config/env"

let orchestratorQueue: Queue | null = null
let validatorQueue: Queue | null = null

export function getOrchestratorQueue(): Queue {
  if (!orchestratorQueue) {
    orchestratorQueue = new Queue("orchestrator", {
      connection: { url: getEnv().REDIS_URL }
    })
  }
  return orchestratorQueue
}

export function getValidatorQueue(): Queue {
  if (!validatorQueue) {
    validatorQueue = new Queue("validator", {
      connection: { url: getEnv().REDIS_URL }
    })
  }
  return validatorQueue
}

export async function closeQueues(): Promise<void> {
  await Promise.all([
    orchestratorQueue?.close().catch(() => undefined),
    validatorQueue?.close().catch(() => undefined)
  ])
  orchestratorQueue = null
  validatorQueue = null
}
