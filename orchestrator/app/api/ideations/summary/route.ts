import { NextResponse } from "next/server"
import { countIdeationByStatus } from "@/lib/repos/ideations.repo"
import { serializeDates } from "@/lib/utils/serialize"

export const runtime = "nodejs"

export async function GET() {
  try {
    const [queued, running, completed, failed] = await Promise.all([
      countIdeationByStatus("QUEUED"),
      countIdeationByStatus("RUNNING"),
      countIdeationByStatus("COMPLETED"),
      countIdeationByStatus("FAILED")
    ])

    return NextResponse.json(
      serializeDates({
        counts: {
          QUEUED: queued,
          RUNNING: running,
          COMPLETED: completed,
          FAILED: failed
        }
      })
    )
  } catch (error) {
    console.error("Failed to fetch ideation summary", error)
    return NextResponse.json({ message: "Internal Server Error" }, { status: 500 })
  }
}
