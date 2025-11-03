import { z } from "zod"

export const IdeationStatusZ = z.enum(["QUEUED", "RUNNING", "COMPLETED", "FAILED"])

export const IdeaJsonZ = z.object({
  Name: z.string(),
  Title: z.string(),
  "Short Hypothesis": z.string(),
  Abstract: z.string(),
  Experiments: z.array(z.string()),
  "Risk Factors and Limitations": z.array(z.string()),
  "Related Work": z.string().optional()
})

export const IdeationRequestZ = z.object({
  _id: z.string().uuid(),
  hypothesisId: z.string().uuid(),
  status: IdeationStatusZ,
  reflections: z.number().int().min(1).max(10),
  createdAt: z.coerce.date(),
  updatedAt: z.coerce.date(),
  startedAt: z.coerce.date().optional(),
  completedAt: z.coerce.date().optional(),
  failedAt: z.coerce.date().optional(),
  error: z.string().optional(),
  ideas: z.array(IdeaJsonZ).optional(),
  claimedBy: z.string().optional(),
  claimedAt: z.coerce.date().optional()
})

export type IdeationStatus = z.infer<typeof IdeationStatusZ>
export type IdeationRequest = z.infer<typeof IdeationRequestZ>
export type IdeaJson = z.infer<typeof IdeaJsonZ>
