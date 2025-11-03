import { getDb } from "../db/mongo"

const COLLECTION = "events_seen"

type EventSeen = {
  _id: string
  runId: string
  processedAt: Date
}

export async function isEventSeen(eventId: string): Promise<boolean> {
  const db = await getDb()
  const doc = await db.collection<EventSeen>(COLLECTION).findOne({ _id: eventId })
  return doc !== null
}

export async function markEventSeen(eventId: string, runId: string): Promise<void> {
  const db = await getDb()
  await db.collection<EventSeen>(COLLECTION).insertOne({
    _id: eventId,
    runId,
    processedAt: new Date()
  })
}

export async function ensureTTLIndex(): Promise<void> {
  const db = await getDb()
  await db.collection(COLLECTION).createIndex(
    { processedAt: 1 },
    { expireAfterSeconds: 7 * 24 * 60 * 60 }
  )
}

