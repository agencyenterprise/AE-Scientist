import { type Filter, type OptionalUnlessRequiredId } from "mongodb"
import { getDb } from "../db/mongo"
import { RunZ, type Run } from "../schemas/run"
import { RUN_STATUSES, type RunStatus } from "../state/constants"

const COLLECTION = "runs"

type ListRunsFilter = Partial<Pick<Run, "hypothesisId">> & {
  status?: RunStatus | RunStatus[]
}

export async function createRun(run: Run): Promise<Run> {
  const dto = RunZ.parse(run)
  const db = await getDb()
  await db.collection<Run>(COLLECTION).insertOne(dto as OptionalUnlessRequiredId<Run>)
  return dto
}

export async function updateRun(id: string, patch: Partial<Run>): Promise<void> {
  const db = await getDb()
  const updateDoc = {
    ...patch,
    updatedAt: new Date()
  }
  await db.collection<Run>(COLLECTION).updateOne({ _id: id }, { $set: updateDoc })
}

export async function findRunById(id: string): Promise<Run | null> {
  const db = await getDb()
  const doc = await db.collection<Run>(COLLECTION).findOne({ _id: id })
  return doc ? RunZ.parse(doc) : null
}

export async function listRuns(
  filter: ListRunsFilter = {},
  page = 1,
  pageSize = 25
): Promise<{ items: Run[]; total: number }> {
  const db = await getDb()
  const query: Filter<Run> = {
    // Filter out hidden runs by default
    hidden: { $ne: true }
  }
  if (filter.hypothesisId) {
    query.hypothesisId = filter.hypothesisId
  }
  if (filter.status) {
    query.status = Array.isArray(filter.status) ? { $in: filter.status } : filter.status
  }
  const collection = db.collection<Run>(COLLECTION)
  const cursor = collection
    .find(query)
    .sort({ createdAt: -1 })
    .skip((page - 1) * pageSize)
    .limit(pageSize)

  const [items, total] = await Promise.all([cursor.toArray(), collection.countDocuments(query)])
  return { items: items.map((item) => RunZ.parse(item)), total }
}

export async function countRunsByStatus(statuses: RunStatus[]): Promise<Record<RunStatus, number>> {
  const db = await getDb()
  const collection = db.collection<Run>(COLLECTION)
  const pipeline = [
    { $match: { status: { $in: statuses }, hidden: { $ne: true } } },
    { $group: { _id: "$status", total: { $sum: 1 } } }
  ]
  const docs = await collection.aggregate<{ _id: RunStatus; total: number }>(pipeline).toArray()
  const counts = Object.fromEntries(RUN_STATUSES.map((status) => [status, 0])) as Record<
    RunStatus,
    number
  >
  docs.forEach((doc) => {
    counts[doc._id] = doc.total
  })
  return counts
}

export async function getHypothesisActivity(limit = 5): Promise<
  Array<{
    hypothesisId: string
    runCount: number
    lastRunAt: Date
  }>
> {
  const db = await getDb()
  const pipeline = [
    { $match: { hidden: { $ne: true } } },
    {
      $group: {
        _id: "$hypothesisId",
        runCount: { $sum: 1 },
        lastRunAt: { $max: "$createdAt" }
      }
    },
    { $sort: { lastRunAt: -1 } },
    { $limit: limit }
  ]
  const docs = await db
    .collection<Run>(COLLECTION)
    .aggregate<{ _id: string; runCount: number; lastRunAt: Date }>(pipeline)
    .toArray()
  return docs.map((doc) => ({
    hypothesisId: doc._id,
    runCount: doc.runCount,
    lastRunAt: new Date(doc.lastRunAt)
  }))
}
