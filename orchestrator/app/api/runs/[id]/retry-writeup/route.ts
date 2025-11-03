import { NextRequest, NextResponse } from "next/server"
import { getDb } from "@/lib/db/mongo"
import { randomUUID } from "crypto"

export const runtime = "nodejs"

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    
    const db = await getDb()
    const runsCollection = db.collection("runs")
    const eventsCollection = db.collection("events")
    
    const run = await runsCollection.findOne({ _id: id })
    
    if (!run) {
      return NextResponse.json(
        { error: "Run not found" },
        { status: 404 }
      )
    }

    if (run.status !== "FAILED" && run.status !== "COMPLETED") {
      return NextResponse.json(
        { error: "Can only retry writeup for failed or completed runs" },
        { status: 400 }
      )
    }

    const existingRetry = await runsCollection.findOne({
      _id: id,
      pendingWriteupRetry: true
    })

    if (existingRetry) {
      return NextResponse.json(
        { error: "Writeup retry already in progress for this run" },
        { status: 409 }
      )
    }
    
    await runsCollection.updateOne(
      { _id: id },
      { 
        $set: { 
          pendingWriteupRetry: true,
          writeupRetryRequestedAt: new Date(),
          writeupRetryRequestedBy: "web-ui"
        } 
      }
    )

    const eventId = randomUUID()
    await eventsCollection.insertOne({
      _id: eventId,
      runId: id,
      timestamp: new Date(),
      type: "ai.run.writeup_retry_requested",
      data: {
        run_id: id,
        requested_by: "web-ui",
        message: "Paper generation retry requested"
      },
      source: "web/retry-writeup",
      seq: (run.lastEventSeq || 0) + 1
    })
    
    return NextResponse.json({
      message: "Paper generation retry queued - a pod worker will pick it up shortly",
      eventId
    })
    
  } catch (error) {
    console.error("Error requesting writeup retry:", error)
    return NextResponse.json(
      { error: "Failed to request writeup retry: " + (error as Error).message },
      { status: 500 }
    )
  }
}

