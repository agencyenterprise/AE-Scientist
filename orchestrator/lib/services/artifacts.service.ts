import { randomUUID } from "node:crypto"
import { createArtifact } from "../repos/artifacts.repo"
import { presignGetObject, presignPutObject, buildPublicUrl } from "../storage/minio"

export async function presignArtifactUpload(runId: string, filename: string) {
  const key = `${runId}/${Date.now()}-${sanitizeFilename(filename)}`
  const url = await presignPutObject(key)
  await createArtifact({
    _id: randomUUID(),
    runId,
    key,
    uri: buildPublicUrl(key),
    createdAt: new Date()
  })
  return { url, key }
}

export async function presignArtifactDownload(key: string) {
  const url = await presignGetObject(key)
  return { url }
}

function sanitizeFilename(filename: string) {
  return filename.replace(/[^\w.-]+/g, "_")
}
