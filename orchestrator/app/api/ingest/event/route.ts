import { NextRequest, NextResponse } from "next/server"
import { CloudEventsEnvelopeZ, validateEventDataWithDetails } from "@/lib/schemas/cloudevents"
import { processEvent } from "@/lib/services/events.service"
import { isEventSeen, markEventSeen } from "@/lib/services/deduplication.service"
import { logger } from "@/lib/logging/logger"

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()

    const envelopeResult = CloudEventsEnvelopeZ.safeParse(body)
    if (!envelopeResult.success) {
      const firstError = envelopeResult.error.errors[0]
      const errorDetails = {
        path: firstError?.path?.join('.') || 'unknown',
        message: firstError?.message || 'Invalid event format',
        received: firstError?.received
      }
      logger.warn({ 
        errors: envelopeResult.error.errors,
        body: JSON.stringify(body).slice(0, 500)
      }, "Invalid CloudEvents envelope")
      return NextResponse.json(
        {
          type: "about:blank",
          title: "Invalid CloudEvents envelope",
          status: 422,
          detail: `Validation failed at ${errorDetails.path}: ${errorDetails.message}`,
          errors: envelopeResult.error.errors.slice(0, 3),
          instance: "/api/ingest/event"
        },
        { status: 422 }
      )
    }

    const event = envelopeResult.data

    const dataValidation = validateEventDataWithDetails(event.type, event.data)
    if (!dataValidation.success) {
      const firstError = dataValidation.errors?.[0]
      logger.warn({ 
        eventType: event.type, 
        eventData: event.data,
        runId: event.subject.replace("run/", ""),
        validationErrors: dataValidation.errors
      }, "Event data validation failed")
      
      return NextResponse.json(
        {
          type: "about:blank",
          title: "Invalid event data",
          status: 422,
          detail: firstError 
            ? `Event data validation failed at '${firstError.path}': ${firstError.message}${firstError.received ? ` (received: ${JSON.stringify(firstError.received)})` : ''}`
            : `Event data does not match schema for type: ${event.type}`,
          errors: dataValidation.errors?.slice(0, 3),
          instance: "/api/ingest/event"
        },
        { status: 422 }
      )
    }

    if (await isEventSeen(event.id)) {
      logger.info({ eventId: event.id }, "Duplicate event ignored")
      return NextResponse.json(
        {
          event_id: event.id,
          status: "duplicate"
        },
        { status: 201 }
      )
    }

    const runId = event.subject.replace("run/", "")
    await markEventSeen(event.id, runId)
    await processEvent(event)

    logger.info({ eventId: event.id, type: event.type }, "Event processed")

    return NextResponse.json(
      {
        event_id: event.id
      },
      { status: 201 }
    )
  } catch (error) {
    logger.error({ error }, "Error processing event")
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Internal server error",
        status: 500,
        detail: error instanceof Error ? error.message : "Unknown error",
        instance: "/api/ingest/event"
      },
      { status: 500 }
    )
  }
}

