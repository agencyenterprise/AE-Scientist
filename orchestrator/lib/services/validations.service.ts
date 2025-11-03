import { randomUUID } from "node:crypto"
import { createValidation, findValidation } from "../repos/validations.repo"
import { transitionRun } from "./runs.service"
import type { Validation } from "../schemas/validation"

type HumanVerdict = "pass" | "fail"

export async function submitHumanValidation(
  runId: string,
  verdict: HumanVerdict,
  notes?: string,
  reviewerId?: string
): Promise<Validation> {
  const validation: Validation = {
    _id: randomUUID(),
    runId,
    kind: "human",
    verdict,
    notes,
    createdAt: new Date(),
    createdBy: reviewerId
  }
  const saved = await createValidation(validation)
  if (verdict === "pass") {
    await transitionRun(runId, "HUMAN_VALIDATED")
  }
  return saved
}

export async function getLatestAutoValidation(runId: string) {
  return findValidation(runId, "auto")
}
