import { NextRequest, NextResponse } from "next/server"
import { CloudEventsEnvelopeZ, validateEventData } from "@/lib/schemas/cloudevents"
import { processEvent } from "@/lib/services/events.service"
import { isEventSeen, markEventSeen } from "@/lib/services/deduplication.service"
import { logger } from "@/lib/logging/logger"

export async function POST(req: NextRequest) {
  try {
    const body = await req.text()
    const lines = body.trim().split("\n")

    let accepted = 0
    let duplicates = 0
    let invalid = 0
    const errors: Array<{ line: number; error: string }> = []

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      if (!line.trim()) continue

      try {
        const eventData = JSON.parse(line)

        const envelopeResult = CloudEventsEnvelopeZ.safeParse(eventData)
        if (!envelopeResult.success) {
          invalid++
          errors.push({
            line: i + 1,
            error: `Invalid CloudEvents envelope: ${envelopeResult.error.errors[0]?.message}`
          })
          continue
        }

        const event = envelopeResult.data

        if (!validateEventData(event.type, event.data)) {
          invalid++
          errors.push({
            line: i + 1,
            error: `Invalid event data for type: ${event.type}`
          })
          continue
        }

        if (await isEventSeen(event.id)) {
          duplicates++
          continue
        }

        const runId = event.subject.replace("run/", "")
        await markEventSeen(event.id, runId)
        await processEvent(event)

        accepted++
      } catch (error) {
        invalid++
        errors.push({
          line: i + 1,
          error: error instanceof Error ? error.message : "Unknown error"
        })
      }
    }

    logger.info({ accepted, duplicates, invalid }, "Batch events processed")

    if (invalid > 0) {
      return NextResponse.json(
        {
          type: "about:blank",
          title: "Batch partially failed",
          status: 207,
          detail: `${accepted} accepted, ${duplicates} duplicates, ${invalid} invalid`,
          instance: "/api/ingest/events",
          accepted,
          duplicates,
          invalid,
          errors
        },
        { status: 207 }
      )
    }

    return NextResponse.json(
      {
        accepted,
        duplicates,
        invalid
      },
      { status: 202 }
    )
  } catch (error) {
    logger.error({ error }, "Error processing batch events")
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Internal server error",
        status: 500,
        detail: error instanceof Error ? error.message : "Unknown error",
        instance: "/api/ingest/events"
      },
      { status: 500 }
    )
  }
}

