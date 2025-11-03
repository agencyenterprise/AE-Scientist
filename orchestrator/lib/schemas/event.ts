import { z } from "zod"

export const EventZ = z.object({
  _id: z.string(),
  runId: z.string().uuid(),
  timestamp: z.coerce.date(),
  type: z.string().min(1),
  data: z.record(z.unknown()),
  source: z.string(),
  seq: z.number().int().optional(),
  message: z.string().nullable().optional(),
  payload: z.record(z.unknown()).optional(),
  level: z.enum(["info", "warn", "error"]).nullable().optional(),
  seed: z.boolean().optional()
})

export type Event = z.infer<typeof EventZ>
