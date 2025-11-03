import { z } from "zod"
import { STAGES } from "../state/constants"

export const StageStatusZ = z.enum(["PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"])

export const StageZ = z.preprocess(
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
    _id: z.string().uuid(),
    runId: z.string().uuid(),
    index: z.number().int().min(0).max(3),
    name: z.enum(STAGES),
    status: StageStatusZ,
    progress: z.number().min(0).max(1).default(0),
    startedAt: z.coerce.date().optional(),
    completedAt: z.coerce.date().optional(),
    summary: z.string().nullable().optional(),
    seed: z.boolean().optional()
  })
)

export type Stage = z.infer<typeof StageZ>
