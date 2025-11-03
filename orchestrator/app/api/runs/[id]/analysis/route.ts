import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { generatePaperAnalysis, getPaperAnalysis } from "@/lib/services/analysis.service"
import { isHttpError, toJsonResponse, createBadRequest } from "@/lib/http/errors"

export const runtime = "nodejs"

const BodySchema = z.object({
  paperId: z.string().min(1),
  paperTitle: z.string().optional(),
  paperUrl: z.string().url().optional(),
  paperContent: z.string().min(100)
})

export async function GET(_: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params
    const analysis = await getPaperAnalysis(id)
    if (!analysis) {
      return NextResponse.json({ message: "Analysis not found" }, { status: 404 })
    }
    return NextResponse.json(analysis)
  } catch (error) {
    return handleError(error)
  }
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params
    const body = await req.json()
    const parsed = BodySchema.safeParse(body)
    if (!parsed.success) {
      throw createBadRequest("Invalid payload", { issues: parsed.error.issues })
    }

    const analysis = await generatePaperAnalysis({
      runId: id,
      paperId: parsed.data.paperId,
      paperTitle: parsed.data.paperTitle,
      paperUrl: parsed.data.paperUrl,
      paperContent: parsed.data.paperContent
    })

    return NextResponse.json(analysis, { status: 201 })
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
