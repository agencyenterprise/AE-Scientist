import { createHash } from "node:crypto"
import { redis } from "../redis/client"

const IDEMPOTENCY_PREFIX = "idem"
const TTL_SECONDS = 24 * 60 * 60

export async function withIdempotency<T>(key: string, create: () => Promise<T>): Promise<T> {
  const cacheKey = hashKey(key)
  const cachedPayload = await redis.get(cacheKey)
  if (cachedPayload) {
    return JSON.parse(cachedPayload) as T
  }
  const result = await create()
  await redis.set(cacheKey, JSON.stringify(result), "EX", TTL_SECONDS)
  return result
}

function hashKey(key: string): string {
  const hash = createHash("sha256").update(key).digest("hex")
  return `${IDEMPOTENCY_PREFIX}:${hash}`
}
