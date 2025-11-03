import { type Filter, type OptionalUnlessRequiredId } from "mongodb"
import { getDb } from "../db/mongo"
import { type ValidationKind, ValidationZ, type Validation } from "../schemas/validation"

const COLLECTION = "validations"

export async function createValidation(validation: Validation): Promise<Validation> {
  const doc = ValidationZ.parse(validation)
  const db = await getDb()
  await db.collection<Validation>(COLLECTION).insertOne(
    doc as OptionalUnlessRequiredId<Validation>
  )
  return doc
}

export async function listValidationsForRun(runId: string): Promise<Validation[]> {
  const db = await getDb()
  const docs = await db
    .collection<Validation>(COLLECTION)
    .find({ runId })
    .sort({ createdAt: -1 })
    .toArray()
  return docs.map((doc) => ValidationZ.parse(doc))
}

export async function findValidation(runId: string, kind: ValidationKind): Promise<Validation | null> {
  const db = await getDb()
  const doc = await db.collection<Validation>(COLLECTION).findOne({ runId, kind } satisfies Filter<Validation>)
  return doc ? ValidationZ.parse(doc) : null
}

export async function listValidationsForRuns(runIds: string[]): Promise<Validation[]> {
  if (runIds.length === 0) {
    return []
  }
  const db = await getDb()
  const docs = await db
    .collection<Validation>(COLLECTION)
    .find({ runId: { $in: runIds } })
    .toArray()
  return docs.map((doc) => ValidationZ.parse(doc))
}
