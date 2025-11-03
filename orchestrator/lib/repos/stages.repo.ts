import { type OptionalUnlessRequiredId } from "mongodb"
import { getDb } from "../db/mongo"
import { StageZ, type Stage } from "../schemas/stage"

const COLLECTION = "stages"

export async function upsertStage(stage: Stage): Promise<void> {
  const doc = StageZ.parse(stage)
  const db = await getDb()
  await db.collection<Stage>(COLLECTION).updateOne(
    { _id: doc._id },
    { $set: doc },
    { upsert: true }
  )
}

export async function createStage(stage: Stage): Promise<Stage> {
  const doc = StageZ.parse(stage)
  const db = await getDb()
  await db.collection<Stage>(COLLECTION).insertOne(doc as OptionalUnlessRequiredId<Stage>)
  return doc
}

export async function updateStage(id: string, patch: Partial<Stage>): Promise<void> {
  const db = await getDb()
  await db.collection<Stage>(COLLECTION).updateOne({ _id: id }, { $set: patch })
}

export async function listStagesForRun(runId: string): Promise<Stage[]> {
  const db = await getDb()
  const docs = await db
    .collection<Stage>(COLLECTION)
    .find({ runId })
    .sort({ index: 1 })
    .toArray()
  return docs.map((doc) => StageZ.parse(doc))
}
