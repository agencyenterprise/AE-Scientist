import { z } from "zod"

export const ArtifactZ = z.object({
  _id: z.string().uuid(),
  runId: z.string().uuid(),
  key: z.string().min(1),
  uri: z.string().min(1),
  hash: z.string().optional(),
  size: z.number().int().nonnegative().optional(),
  contentType: z.string().optional(),
  createdAt: z.coerce.date(),
  description: z.string().optional(),
  seed: z.boolean().optional()
})

export type Artifact = z.infer<typeof ArtifactZ>
