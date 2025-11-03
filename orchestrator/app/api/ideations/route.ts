import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import {
  listIdeationRequests,
  countIdeationByStatus
} from "@/lib/repos/ideations.repo"
import { findHypothesesByIds } from "@/lib/repos/hypotheses.repo"
import { IdeationStatusZ } from "@/lib/schemas/ideation"
import { serializeDates } from "@/lib/utils/serialize"

export const runtime = "nodejs"

const QuerySchema = z.object({
  page: z.coerce.number().min(1).default(1),
  pageSize: z.coerce.number().min(1).max(100).default(25),
  status: IdeationStatusZ.optional(),
  hypothesisId: z.string().uuid().optional()
})

export async function GET(req: NextRequest) {
  try {
    const url = new URL(req.url)
    const parsed = QuerySchema.safeParse(Object.fromEntries(url.searchParams))
    if (!parsed.success) {
      return NextResponse.json(
        { message: "Invalid query", issues: parsed.error.issues },
        { status: 400 }
      )
    }

    const filter: Record<string, unknown> = {}
    if (parsed.data.status) {
      filter.status = parsed.data.status
    }
    if (parsed.data.hypothesisId) {
      filter.hypothesisId = parsed.data.hypothesisId
    }
    const [{ items, total }, queued, running, completed, failed] = await Promise.all([
      listIdeationRequests(filter, parsed.data.page, parsed.data.pageSize),
      countIdeationByStatus("QUEUED"),
      countIdeationByStatus("RUNNING"),
      countIdeationByStatus("COMPLETED"),
      countIdeationByStatus("FAILED")
    ])

    const hypothesisIds = Array.from(new Set(items.map((item) => item.hypothesisId)))
    const hypotheses = await findHypothesesByIds(hypothesisIds)
    const hypothesisMap = new Map(hypotheses.map((hypothesis) => [hypothesis._id, hypothesis]))

    return NextResponse.json(
      serializeDates({
        items: items.map((item) => ({
          ...item,
          hypothesis: hypothesisMap.get(item.hypothesisId) ?? null
        })),
        total,
        page: parsed.data.page,
        pageSize: parsed.data.pageSize,
        counts: {
          QUEUED: queued,
          RUNNING: running,
          COMPLETED: completed,
          FAILED: failed
        }
      })
    )
  } catch (error) {
    console.error("Failed to list ideations", error)
    return NextResponse.json(
      { message: "Internal Server Error" },
      { status: 500 }
    )
  }
}
