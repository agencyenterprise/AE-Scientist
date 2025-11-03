import { NextRequest, NextResponse } from "next/server"
import { updateRun, findRunById } from "@/lib/repos/runs.repo"

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: runId } = await params
    
    const run = await findRunById(runId)
    if (!run) {
      return NextResponse.json(
        { error: "Run not found" },
        { status: 404 }
      )
    }
    
    const cancelableStatuses = ["QUEUED", "SCHEDULED", "STARTING", "RUNNING"]
    if (!cancelableStatuses.includes(run.status)) {
      return NextResponse.json(
        { error: `Cannot cancel run in status: ${run.status}` },
        { status: 400 }
      )
    }
    
    await updateRun(runId, {
      status: "CANCELED",
      updatedAt: new Date()
    })
    
    return NextResponse.json({ success: true })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
