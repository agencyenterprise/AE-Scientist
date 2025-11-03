import Redis from "ioredis"
import { getEnv } from "../config/env"

declare global {
  // eslint-disable-next-line no-var
  var __redisClient: Redis | undefined
}

function createClient(): Redis {
  const env = getEnv()
  return new Redis(env.REDIS_URL, {
    maxRetriesPerRequest: null,
    enableReadyCheck: false,
    lazyConnect: true
  })
}

export const redis: Redis =
  global.__redisClient ??
  (() => {
    const client = createClient()
    if (envIsDev()) {
      global.__redisClient = client
    }
    return client
  })()

function envIsDev() {
  const env = getEnv()
  return env.NODE_ENV === "development" || env.NODE_ENV === "test"
}
