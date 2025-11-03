import { NextResponse } from "next/server"
import { getOverviewData } from "@/lib/data/overview"

export const dynamic = "force-dynamic"

export async function GET() {
  try {
    const data = await getOverviewData()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error fetching overview data:", error)
    return NextResponse.json(
      { error: "Failed to fetch overview data" },
      { status: 500 }
    )
  }
}


