import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { listRuns } from "@/lib/repos/runs.repo"
import { RUN_STATUSES } from "@/lib/state/constants"
import { isHttpError, toJsonResponse } from "@/lib/http/errors"

export const runtime = "nodejs"

const QuerySchema = z.object({
  status: z.enum(RUN_STATUSES).optional(),
  hypothesisId: z.string().uuid().optional(),
  page: z.coerce.number().min(1).default(1),
  pageSize: z.coerce.number().min(1).max(100).default(25)
})

export async function GET(req: NextRequest) {
  try {
    const searchParams = Object.fromEntries(new URL(req.url).searchParams)
    const parsed = QuerySchema.safeParse(searchParams)
    if (!parsed.success) {
      return NextResponse.json(
        { message: "Invalid query", issues: parsed.error.issues },
        { status: 400 }
      )
    }
    const { items, total } = await listRuns(
      {
        status: parsed.data.status,
        hypothesisId: parsed.data.hypothesisId
      },
      parsed.data.page,
      parsed.data.pageSize
    )
    return NextResponse.json({
      items,
      total,
      page: parsed.data.page,
      pageSize: parsed.data.pageSize
    })
  } catch (error) {
    return handleError(error)
  }
}

function handleError(error: unknown) {
  if (error instanceof Response) {
    return error
  }
  if (isHttpError(error)) {
    return toJsonResponse(error)
  }
  return new Response(JSON.stringify({ message: "Internal Server Error" }), {
    status: 500,
    headers: { "content-type": "application/json" }
  })
}
