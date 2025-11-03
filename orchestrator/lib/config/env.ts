import "dotenv/config"
import { z } from "zod"

const booleanString = z
  .string()
  .transform((value) => value === "true")
  .pipe(z.boolean())

const numberString = z
  .string()
  .transform((value) => Number.parseInt(value, 10))
  .refine((value) => Number.isFinite(value), "must be a number")

const EnvSchema = z
  .object({
    NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
    MONGODB_URI: z.string().url(),
    MONGODB_DB: z.string().min(1),
    REDIS_URL: z.string().min(1),
    MINIO_ENDPOINT: z.string().min(1),
    MINIO_PORT: z
      .string()
      .transform((value) => Number.parseInt(value, 10))
      .optional(),
    MINIO_USE_SSL: booleanString,
    MINIO_ACCESS_KEY: z.string().min(1),
    MINIO_SECRET_KEY: z.string().min(1),
    MINIO_BUCKET: z.string().min(1),
    MINIO_REGION: z.string().min(1),
    MINIO_PUBLIC_BASE_URL: z.string().url(),
    POD_SEMAPHORE_KEY: z.string().min(1).optional(),
    MAX_POD_SLOTS: numberString.optional(),
    GPU_SEMAPHORE_KEY: z.string().min(1).optional(),
    GPU_MAX_SLOTS: numberString.optional(),
    OPENAI_API_KEY: z.string().min(1).optional(),
    OPENAI_MODEL_QUANT: z.string().min(1).optional(),
    OPENAI_MODEL_QUAL: z.string().min(1).optional()
  })
  .transform((env) => {
    const semaphoreKey = env.POD_SEMAPHORE_KEY ?? env.GPU_SEMAPHORE_KEY
    if (!semaphoreKey) {
      throw new Error("POD_SEMAPHORE_KEY is required (fallback GPU_SEMAPHORE_KEY accepted)")
    }
    const maxSlots = env.MAX_POD_SLOTS ?? env.GPU_MAX_SLOTS ?? 4
    return {
      ...env,
      POD_SEMAPHORE_KEY: semaphoreKey,
      MAX_POD_SLOTS: maxSlots
    }
  })

export type Env = z.infer<typeof EnvSchema>

let cachedEnv: Env | null = null

export function getEnv(): Env {
  if (cachedEnv) {
    return cachedEnv
  }
  
  const hasRequiredEnvVars = process.env.MONGODB_URI && process.env.REDIS_URL && process.env.MINIO_ENDPOINT
  
  if (!hasRequiredEnvVars) {
    return {
      NODE_ENV: (process.env.NODE_ENV as "development" | "production" | "test") || "production",
      MONGODB_URI: "mongodb://localhost:27017",
      MONGODB_DB: "build",
      REDIS_URL: "redis://localhost:6379",
      MINIO_ENDPOINT: "localhost",
      MINIO_PORT: 9000,
      MINIO_USE_SSL: false,
      MINIO_ACCESS_KEY: "build",
      MINIO_SECRET_KEY: "build",
      MINIO_BUCKET: "build",
      MINIO_REGION: "us-east-1",
      MINIO_PUBLIC_BASE_URL: "http://localhost:9000",
      POD_SEMAPHORE_KEY: "build",
      MAX_POD_SLOTS: 4,
      GPU_SEMAPHORE_KEY: undefined,
      GPU_MAX_SLOTS: undefined,
      OPENAI_API_KEY: undefined,
      OPENAI_MODEL_QUANT: undefined,
      OPENAI_MODEL_QUAL: undefined
    } as Env
  }
  
  const parsed = EnvSchema.safeParse(process.env)
  if (!parsed.success) {
    throw new Error(`Invalid environment variables: ${parsed.error.message}`)
  }
  cachedEnv = parsed.data
  return cachedEnv
}
