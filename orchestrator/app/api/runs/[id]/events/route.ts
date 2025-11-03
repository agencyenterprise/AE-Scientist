import { NextRequest, NextResponse } from "next/server"
import { listEvents } from "@/lib/repos/events.repo"

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: runId } = await params
    const url = new URL(req.url)
    
    const type = url.searchParams.get("type")
    const level = url.searchParams.get("level")
    const page = parseInt(url.searchParams.get("page") || "1")
    const pageSize = parseInt(url.searchParams.get("pageSize") || "100")
    
    const { items, total } = await listEvents(runId, page, pageSize)
    
    let filtered = items
    if (type) {
      filtered = filtered.filter(e => e.type === type)
    }
    if (level) {
      filtered = filtered.filter(e => e.data?.level === level)
    }
    
    return NextResponse.json({
      items: filtered,
      total: filtered.length,
      page,
      pageSize
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    )
  }
}
