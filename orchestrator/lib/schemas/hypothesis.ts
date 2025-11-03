import { z } from "zod"
import { IdeaJsonZ, IdeationStatusZ } from "./ideation"

export const HypothesisZ = z.object({
  _id: z.string().uuid(),
  title: z.string().min(3),
  idea: z.string().min(10),
  createdAt: z.coerce.date(),
  createdBy: z.string().min(1),
  updatedAt: z.coerce.date().optional(),
  seed: z.boolean().optional(),
  ideaJson: z.record(z.any()).optional(),
  chatGptUrl: z.string().optional(),
  extractionStatus: z.enum(["pending", "extracting", "completed", "failed"]).optional(),
  ideation: z
    .object({
      requestId: z.string().uuid(),
      status: IdeationStatusZ,
      reflections: z.number().int().min(1).max(10),
      startedAt: z.coerce.date().optional(),
      completedAt: z.coerce.date().optional(),
      failedAt: z.coerce.date().optional(),
      error: z.string().optional(),
      ideas: z.array(IdeaJsonZ).optional()
    })
    .optional(),
  hidden: z.boolean().optional()
})

export type Hypothesis = z.infer<typeof HypothesisZ>
