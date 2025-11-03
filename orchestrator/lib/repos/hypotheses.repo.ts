import { type Filter, type OptionalUnlessRequiredId } from "mongodb"
import { getDb } from "../db/mongo"
import { HypothesisZ, type Hypothesis } from "../schemas/hypothesis"

const COLLECTION = "hypotheses"

export async function createHypothesis(doc: Hypothesis): Promise<Hypothesis> {
  const validDoc = HypothesisZ.parse(doc)
  const db = await getDb()
  await db.collection<Hypothesis>(COLLECTION).insertOne(
    validDoc as OptionalUnlessRequiredId<Hypothesis>
  )
  return validDoc
}

export async function listHypotheses(
  filter: Filter<Hypothesis> = {},
  page = 1,
  pageSize = 25
): Promise<{ items: Hypothesis[]; total: number }> {
  const db = await getDb()
  const collection = db.collection<Hypothesis>(COLLECTION)
  const query: Filter<Hypothesis> = { ...filter }
  if (query.hidden === undefined) {
    ;(query as any).hidden = { $ne: true }
  }
  const cursor = collection
    .find(query)
    .sort({ createdAt: -1 })
    .skip((page - 1) * pageSize)
    .limit(pageSize)
  const [items, total] = await Promise.all([cursor.toArray(), collection.countDocuments(query)])
  return {
    items: items.map((item) => HypothesisZ.parse(item)),
    total
  }
}

export async function findHypothesisById(id: string): Promise<Hypothesis | null> {
  const db = await getDb()
  const doc = await db.collection<Hypothesis>(COLLECTION).findOne({ _id: id })
  return doc ? HypothesisZ.parse(doc) : null
}

export async function findHypothesesByIds(ids: string[]): Promise<Hypothesis[]> {
  if (ids.length === 0) {
    return []
  }
  const db = await getDb()
  const docs = await db
    .collection<Hypothesis>(COLLECTION)
    .find({ _id: { $in: ids } })
    .toArray()
  return docs.map((doc) => HypothesisZ.parse(doc))
}

export async function updateHypothesis(
  id: string,
  updates: Partial<Hypothesis>
): Promise<Hypothesis | null> {
  const db = await getDb()
  const result = await db.collection<Hypothesis>(COLLECTION).findOneAndUpdate(
    { _id: id },
    { $set: { ...updates, updatedAt: new Date() } },
    { returnDocument: "after" }
  )
  return result ? HypothesisZ.parse(result) : null
}
