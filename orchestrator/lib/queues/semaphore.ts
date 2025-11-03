import { Semaphore } from "redis-semaphore"
import { redis } from "../redis/client"
import { getEnv } from "../config/env"

let semaphore: Semaphore | null = null

export function getPodSemaphore(): Semaphore {
  if (!semaphore) {
    const env = getEnv()
    semaphore = new Semaphore(redis, env.POD_SEMAPHORE_KEY, env.MAX_POD_SLOTS, {
      lockTimeout: 5 * 60 * 1000,
      acquireTimeout: 30 * 1000
    })
  }
  return semaphore
}
