import pino from "pino"
import { getEnv } from "../config/env"

let loggerInstance: pino.Logger | null = null

function getLogger(): pino.Logger {
  if (!loggerInstance) {
    const env = getEnv()
    loggerInstance = pino({
      level: env.NODE_ENV === "production" ? "info" : "debug",
      base: undefined
    })
  }
  return loggerInstance
}

export const logger = new Proxy({} as pino.Logger, {
  get(_, prop) {
    return getLogger()[prop as keyof pino.Logger]
  }
})

export function createLogger(context: Record<string, unknown>) {
  return getLogger().child(context)
}
