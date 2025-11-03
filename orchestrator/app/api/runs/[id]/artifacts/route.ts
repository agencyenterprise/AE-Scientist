import { NextRequest, NextResponse } from "next/server"
import { listArtifactsForRun } from "@/lib/repos/artifacts.repo"

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: runId } = await params
    const artifacts = await listArtifactsForRun(runId)
    
    return NextResponse.json(artifacts)
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to fetch artifacts" },
      { status: 500 }
    )
  }
}

