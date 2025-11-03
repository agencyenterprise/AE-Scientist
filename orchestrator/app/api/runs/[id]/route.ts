import { NextResponse } from "next/server"
import { getRunDetail } from "@/lib/data/runs"
import { toJsonResponse, createNotFound, isHttpError } from "@/lib/http/errors"

export const runtime = "nodejs"

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params
    const detail = await getRunDetail(id)
    if (!detail) {
      throw createNotFound("Run not found")
    }
    return NextResponse.json(detail)
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
