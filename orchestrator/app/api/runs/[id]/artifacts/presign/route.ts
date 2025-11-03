import { NextRequest, NextResponse } from "next/server"
import { getEnv } from "@/lib/config/env"
import { Client } from "minio"

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: runId } = await params
    const body = await req.json()
    const { action, filename, key, content_type } = body
    
    const env = getEnv()
    const minioClient = new Client({
      endPoint: env.MINIO_ENDPOINT,
      port: env.MINIO_PORT,
      useSSL: env.MINIO_USE_SSL,
      accessKey: env.MINIO_ACCESS_KEY,
      secretKey: env.MINIO_SECRET_KEY
    })
    
    let url: string
    
    if (action === "put") {
      // For upload
      const objectKey = key || `runs/${runId}/${filename}`
      
      url = await minioClient.presignedPutObject(
        env.MINIO_BUCKET,
        objectKey,
        24 * 60 * 60 // 24 hours
      )
    } else if (action === "get") {
      // For download
      const objectKey = key || `runs/${runId}/${filename}`
      
      url = await minioClient.presignedGetObject(
        env.MINIO_BUCKET,
        objectKey,
        24 * 60 * 60 // 24 hours
      )
    } else {
      return NextResponse.json(
        { error: "Invalid action. Use 'put' or 'get'" },
        { status: 400 }
      )
    }
    
    return NextResponse.json({ url })
    
  } catch (error) {
    console.error("Error generating presigned URL:", error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to generate presigned URL" },
      { status: 500 }
    )
  }
}
