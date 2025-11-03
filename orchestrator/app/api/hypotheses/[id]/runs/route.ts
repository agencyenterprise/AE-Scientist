import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { listRuns } from "@/lib/repos/runs.repo"
import { enqueueRun } from "@/lib/services/runs.service"
import { withIdempotency } from "@/lib/http/Idempotency"
import { createBadRequest, createNotFound, isHttpError, toJsonResponse } from "@/lib/http/errors"
import { findHypothesisById } from "@/lib/repos/hypotheses.repo"

export const runtime = "nodejs"

const CreateRunSchema = z.object({
  metadata: z.record(z.unknown()).optional()
})

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const page = Number(new URL(req.url).searchParams.get("page") ?? 1)
    const pageSize = Number(new URL(req.url).searchParams.get("pageSize") ?? 25)
    const { items, total } = await listRuns({ hypothesisId: id }, page, pageSize)
    return NextResponse.json({ items, total, page, pageSize })
  } catch (error) {
    return handleError(error)
  }
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const hypothesis = await findHypothesisById(id)
    if (!hypothesis) {
      throw createNotFound("Hypothesis not found")
    }
    const body = await req.json().catch(() => ({}))
    const parsed = CreateRunSchema.safeParse(body)
    if (!parsed.success) {
      throw createBadRequest("Invalid payload", { issues: parsed.error.issues })
    }

    const key = req.headers.get("Idempotency-Key")
    if (!key) {
      throw createBadRequest("Missing Idempotency-Key header")
    }

    const run = await withIdempotency(key, () => enqueueRun(id))
    return NextResponse.json(run, { status: 201 })
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
