import { z } from "zod"

export const ValidationKindZ = z.enum(["auto", "human"])
export type ValidationKind = z.infer<typeof ValidationKindZ>

export const ValidationZ = z.object({
  _id: z.string().uuid(),
  runId: z.string().uuid(),
  kind: ValidationKindZ,
  verdict: z.enum(["pass", "fail"]),
  rubric: z.record(z.number()).optional(),
  notes: z.string().optional(),
  createdAt: z.coerce.date(),
  createdBy: z.string().optional(),
  seed: z.boolean().optional()
})

export type Validation = z.infer<typeof ValidationZ>
