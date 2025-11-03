import { NextRequest, NextResponse } from "next/server"
import { findHypothesisById, updateHypothesis } from "@/lib/repos/hypotheses.repo"
import { listRuns } from "@/lib/repos/runs.repo"
import { cancelRun } from "@/lib/services/runs.service"

export const runtime = "nodejs"

const CANCELABLE_STATUSES = ["QUEUED", "SCHEDULED", "STARTING", "RUNNING"] as const

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params

    const hypothesis = await findHypothesisById(id)
    if (!hypothesis) {
      return NextResponse.json({ success: false, error: "Hypothesis not found" }, { status: 404 })
    }

    const { items: runs } = await listRuns({ hypothesisId: id }, 1, 200)
    const cancelled: string[] = []
    for (const run of runs) {
      if (CANCELABLE_STATUSES.includes(run.status)) {
        try {
          await cancelRun(run._id)
          cancelled.push(run._id)
        } catch (error) {
          console.error(`Failed to cancel run ${run._id}:`, error)
        }
      }
    }

    await updateHypothesis(id, { hidden: true })

    return NextResponse.json({ success: true, cancelledRunIds: cancelled })
  } catch (error) {
    console.error("Hide hypothesis error:", error)
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Failed to hide hypothesis"
      },
      { status: 500 }
    )
  }
}
