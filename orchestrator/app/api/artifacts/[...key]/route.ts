import { NextRequest, NextResponse } from "next/server"
import { getEnv } from "@/lib/config/env"
import { Client } from "minio"

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ key: string[] }> }
) {
  try {
    const { key } = await params
    const decodedKey = key.map(decodeURIComponent).join('/')
    
    const env = getEnv()
    const minioClient = new Client({
      endPoint: env.MINIO_ENDPOINT,
      port: env.MINIO_PORT,
      useSSL: env.MINIO_USE_SSL,
      accessKey: env.MINIO_ACCESS_KEY,
      secretKey: env.MINIO_SECRET_KEY
    })
    
    // Get presigned URL for fetching
    const url = await minioClient.presignedGetObject(
      env.MINIO_BUCKET,
      decodedKey,
      24 * 60 * 60 // 24 hours
    )
    
    // Redirect to MinIO URL
    return NextResponse.redirect(url)
    
  } catch (error) {
    console.error("Error fetching artifact:", error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to fetch artifact" },
      { status: 500 }
    )
  }
}

