import "dotenv/config"
import { minio, buildPublicUrl } from "@/lib/storage/minio"
import { getEnv } from "@/lib/config/env"

async function main() {
  const env = getEnv()
  
  console.info("MinIO Configuration:")
  console.info(`  Endpoint: ${env.MINIO_ENDPOINT}`)
  console.info(`  Port: ${env.MINIO_PORT || 'default'}`)
  console.info(`  Use SSL: ${env.MINIO_USE_SSL}`)
  console.info(`  Region: ${env.MINIO_REGION}`)
  console.info(`  Bucket: ${env.MINIO_BUCKET}`)
  console.info(`  Access Key: ${env.MINIO_ACCESS_KEY.slice(0, 4)}***`)
  console.info("")
  
  const bucket = env.MINIO_BUCKET
  console.info(`Checking if bucket "${bucket}" exists...`)
  const exists = await minio.bucketExists(bucket)
  if (!exists) {
    console.info(`Bucket "${bucket}" does not exist. Attempting to create it...`)
    try {
      await minio.makeBucket(bucket, env.MINIO_REGION)
      console.info(`✓ Successfully created bucket "${bucket}"`)
    } catch (error) {
      console.error(`✗ Failed to create bucket "${bucket}":`, error)
      console.info(`\nManual steps:`)
      console.info(`  1. Visit: https://console-production-541d.up.railway.app`)
      console.info(`  2. Log in with access key: ${env.MINIO_ACCESS_KEY}`)
      console.info(`  3. Click "Create Bucket"`)
      console.info(`  4. Name it: ${bucket}`)
      console.info(`  5. Region: ${env.MINIO_REGION}`)
      process.exitCode = 1
      return
    }
  }

  console.info(`Bucket "${bucket}" is reachable.`)

  const objects = await listSampleObjects(bucket)
  if (objects.length === 0) {
    console.info("No objects found. Uploads will appear once runs produce artifacts.")
  } else {
    console.info("Sample objects:")
    for (const object of objects) {
      console.info(`  • ${object.name} (${object.size} bytes) → ${buildPublicUrl(object.name)}`)
    }
  }

  // Attempt a presign to ensure credentials are correct
  const testKey = `${bucket}-connectivity-check-${Date.now()}.txt`
  const uploadUrl = await minio.presignedPutObject(bucket, testKey, 60)
  const downloadUrl = await minio.presignedGetObject(bucket, testKey, 60)
  console.info("Generated presigned URLs (valid 60s):")
  console.info(`  PUT ${uploadUrl}`)
  console.info(`  GET ${downloadUrl}`)
  console.info("MinIO connectivity check complete. (No objects uploaded.)")
}

async function listSampleObjects(bucket: string) {
  const stream = minio.listObjectsV2(bucket, "", true, "")
  const objects: Array<{ name: string; size: number }> = []
  let count = 0
  const maxObjects = 5
  return new Promise<typeof objects>((resolve, reject) => {
    stream.on("data", (obj) => {
      if (count >= maxObjects) {
        stream.destroy()
        resolve(objects)
        return
      }
      if (obj && typeof obj.name === "string") {
        objects.push({ name: obj.name, size: obj.size ?? 0 })
        count++
      }
    })
    stream.on("error", (error) => reject(error))
    stream.on("end", () => resolve(objects))
  })
}

main().catch((error) => {
  console.error("MinIO connectivity check failed:", error)
  process.exitCode = 1
})
