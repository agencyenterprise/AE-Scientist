import { NextRequest, NextResponse } from "next/server"
import { z } from "zod"
import { createHypothesis, listHypotheses } from "@/lib/repos/hypotheses.repo"
import { createBadRequest, isHttpError, toJsonResponse } from "@/lib/http/errors"
import { enqueueRun } from "@/lib/services/runs.service"
import { generateIdeaJson } from "@/lib/services/ideation.service"
import { createIdeationRequest } from "@/lib/repos/ideations.repo"
import { type IdeationStatus } from "@/lib/schemas/ideation"
import { randomUUID } from "node:crypto"

export const runtime = "nodejs"

const CreateHypothesisSchema = z
  .object({
    title: z.string().min(3),
    idea: z.string().min(10),
    createdBy: z.string().min(1).default("system"),
    enableIdeation: z.boolean().optional().default(false),
    reflections: z.coerce.number().int().min(1).max(10).default(3)
  })
  .refine(
    (data) =>
      !data.enableIdeation ||
      (Number.isInteger(data.reflections) && data.reflections >= 1 && data.reflections <= 10),
    {
      message: "Ideation requires a reflection count between 1 and 10",
      path: ["reflections"]
    }
  )

const QuerySchema = z.object({
  page: z.coerce.number().min(1).default(1),
  pageSize: z.coerce.number().min(1).max(100).default(50)
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
    const { items, total } = await listHypotheses({}, parsed.data.page, parsed.data.pageSize)
    
    // Filter out test hypotheses (those with titles ending in "Test")
    const filteredItems = items.filter(h => !h.title.endsWith(" Test"))
    
    return NextResponse.json({
      items: filteredItems,
      total: filteredItems.length,
      page: parsed.data.page,
      pageSize: parsed.data.pageSize
    })
  } catch (error) {
    return handleError(error)
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const parsed = CreateHypothesisSchema.safeParse(body)
    if (!parsed.success) {
      throw createBadRequest("Invalid payload", { issues: parsed.error.issues })
    }

    const enableIdeation = parsed.data.enableIdeation ?? false
    const reflections = parsed.data.reflections ?? 3
    const hypothesisId = randomUUID()
    const now = new Date()

    if (enableIdeation) {
      const requestId = randomUUID()
      const hypothesis = await createHypothesis({
        _id: hypothesisId,
        title: parsed.data.title,
        idea: parsed.data.idea,
        createdAt: now,
        createdBy: parsed.data.createdBy,
        ideation: {
          requestId,
          status: "QUEUED" as IdeationStatus,
          reflections
        }
      })

      await createIdeationRequest({
        _id: requestId,
        hypothesisId,
        status: "QUEUED",
        reflections,
        createdAt: now,
        updatedAt: now
      })

      return NextResponse.json(
        {
          hypothesis,
          ideation: {
            requestId,
            redirectUrl: `/ideation?hypothesisId=${hypothesisId}`
          }
        },
        { status: 201 }
      )
    }

    const ideaJson = await generateIdeaJson(parsed.data.title, parsed.data.idea).catch(() => ({
      Name: parsed.data.title.toLowerCase().replace(/\s+/g, "_"),
      Title: parsed.data.title,
      "Short Hypothesis": parsed.data.idea.slice(0, 200),
      Abstract: parsed.data.idea,
      Experiments: [
        "Implement the proposed approach",
        "Test on relevant datasets",
        "Evaluate performance metrics"
      ],
      "Risk Factors and Limitations": [
        "Computational complexity",
        "Generalization to other domains"
      ]
    }))

    const hypothesis = await createHypothesis({
      _id: hypothesisId,
      title: parsed.data.title,
      idea: parsed.data.idea,
      ideaJson,
      createdAt: now,
      createdBy: parsed.data.createdBy
    })

    await enqueueRun(hypothesis._id)

    return NextResponse.json(hypothesis, { status: 201 })
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
