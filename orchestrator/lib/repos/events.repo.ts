import { type OptionalUnlessRequiredId } from "mongodb"
import { getDb } from "../db/mongo"
import { EventZ, type Event } from "../schemas/event"

const COLLECTION = "events"

export async function appendEvent(event: Event): Promise<Event> {
  const doc = EventZ.parse(event)
  const db = await getDb()
  await db.collection<Event>(COLLECTION).insertOne(doc as OptionalUnlessRequiredId<Event>)
  return doc
}

export async function createEvent(event: Event): Promise<Event> {
  const doc = EventZ.parse(event)
  const db = await getDb()
  await db.collection<Event>(COLLECTION).insertOne(doc as OptionalUnlessRequiredId<Event>)
  return doc
}

export async function listEvents(
  runId: string,
  page = 1,
  pageSize = 100
): Promise<{ items: Event[]; total: number }> {
  const db = await getDb()
  const collection = db.collection<Event>(COLLECTION)
  const query = { runId }
  const cursor = collection
    .find(query)
    .sort({ timestamp: -1 })
    .skip((page - 1) * pageSize)
    .limit(pageSize)

  const [items, total] = await Promise.all([cursor.toArray(), collection.countDocuments(query)])
  return { items: items.map((item) => EventZ.parse(item)), total }
}
