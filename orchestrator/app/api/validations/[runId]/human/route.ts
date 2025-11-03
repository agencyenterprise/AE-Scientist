import { NextRequest } from "next/server"
import { z } from "zod"
import { submitHumanValidation } from "@/lib/services/validations.service"
import { createBadRequest, isHttpError, toJsonResponse } from "@/lib/http/errors"

export const runtime = "nodejs"

const Schema = z.object({
  verdict: z.enum(["pass", "fail"]),
  notes: z.string().optional(),
  reviewerId: z.string().optional()
})

export async function POST(req: NextRequest, { params }: { params: Promise<{ runId: string }> }) {
  try {
    const { runId } = await params
    const body = await req.json()
    const parsed = Schema.safeParse(body)
    if (!parsed.success) {
      throw createBadRequest("Invalid payload", { issues: parsed.error.issues })
    }
    await submitHumanValidation(runId, parsed.data.verdict, parsed.data.notes, parsed.data.reviewerId)
    return new Response(null, { status: 204 })
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
