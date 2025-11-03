import { RUN_STATUSES, type RunStatus } from "./constants"

type TransitionGraph = Record<RunStatus, ReadonlyArray<RunStatus>>

const TRANSITIONS: TransitionGraph = {
  QUEUED: ["SCHEDULED", "CANCELED"],
  SCHEDULED: ["STARTING", "RUNNING", "FAILED", "CANCELED"],
  STARTING: ["RUNNING", "FAILED", "CANCELED"],
  RUNNING: ["AUTO_VALIDATING", "FAILED", "CANCELED", "COMPLETED"],
  AUTO_VALIDATING: ["AWAITING_HUMAN", "FAILED", "CANCELED"],
  AWAITING_HUMAN: ["HUMAN_VALIDATED", "FAILED", "CANCELED"],
  HUMAN_VALIDATED: [],
  FAILED: [],
  CANCELED: [],
  COMPLETED: ["AUTO_VALIDATING", "AWAITING_HUMAN", "HUMAN_VALIDATED", "FAILED", "CANCELED"]
}

export function assertTransition(from: RunStatus, to: RunStatus): void {
  const allowed = TRANSITIONS[from] ?? []
  if (!allowed.includes(to)) {
    throw new Error(`Illegal run transition ${from} → ${to}`)
  }
}

export function isTerminal(status: RunStatus): boolean {
  return TRANSITIONS[status]?.length === 0
}

export const ALL_STATUSES = RUN_STATUSES
