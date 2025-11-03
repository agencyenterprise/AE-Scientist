import { Client } from "minio"
import { getEnv } from "../config/env"

const env = getEnv()
const endpoint = resolveEndpoint(env.MINIO_ENDPOINT, env.MINIO_USE_SSL)

export const minio = new Client({
  endPoint: endpoint.hostname,
  port: env.MINIO_PORT ?? (endpoint.port ? Number.parseInt(endpoint.port, 10) : undefined),
  useSSL: endpoint.protocol === "https:",
  accessKey: env.MINIO_ACCESS_KEY,
  secretKey: env.MINIO_SECRET_KEY,
  region: env.MINIO_REGION
})

export async function presignPutObject(key: string, expirySeconds = 900): Promise<string> {
  return minio.presignedPutObject(env.MINIO_BUCKET, key, expirySeconds)
}

export async function presignGetObject(key: string, expirySeconds = 900): Promise<string> {
  return minio.presignedGetObject(env.MINIO_BUCKET, key, expirySeconds)
}

export function buildPublicUrl(key: string): string {
  return `${env.MINIO_PUBLIC_BASE_URL.replace(/\/$/, "")}/${key}`
}

function resolveEndpoint(value: string, useSsl: boolean): URL {
  if (value.startsWith("http://") || value.startsWith("https://")) {
    return new URL(value)
  }
  const protocol = useSsl ? "https" : "http"
  return new URL(`${protocol}://${value}`)
}
