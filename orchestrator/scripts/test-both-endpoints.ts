import "dotenv/config"
import { Client } from "minio"

const endpoints = [
  { name: "Console", url: "console-production-541d.up.railway.app" },
  { name: "Bucket", url: "bucket-production-cafb.up.railway.app" }
]

const accessKey = "hyKCZgqlsU8SH8VF4wT4"
const secretKey = "EVpVU4AeYG4Q6U8KkhGb2PJg0UITQae2B2N9pJM0"

async function testEndpoint(name: string, endpoint: string) {
  console.log(`\n=== Testing ${name} Service: ${endpoint} ===`)
  
  const client = new Client({
    endPoint: endpoint,
    useSSL: true,
    accessKey,
    secretKey,
    region: "us-west-2"
  })
  
  try {
    console.log("  Checking bucket 'ai-scientist'...")
    const exists = await client.bucketExists("ai-scientist")
    console.log(`  ✓ Bucket exists: ${exists}`)
    
    if (!exists) {
      console.log("  Attempting to list all buckets...")
      const buckets = await client.listBuckets()
      console.log(`  ✓ Found ${buckets.length} bucket(s):`)
      for (const bucket of buckets) {
        console.log(`    - ${bucket.name}`)
      }
    }
  } catch (error: any) {
    console.log(`  ✗ Error: ${error.message}`)
    console.log(`  Code: ${error.code}`)
  }
}

async function main() {
  for (const endpoint of endpoints) {
    await testEndpoint(endpoint.name, endpoint.url)
  }
}

main().catch(console.error)

