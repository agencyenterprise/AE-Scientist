import { type Filter, type OptionalUnlessRequiredId } from "mongodb"
import { getDb } from "../db/mongo"
import {
  IdeationRequestZ,
  type IdeationRequest,
  type IdeationStatus
} from "../schemas/ideation"

const COLLECTION = "ideation_requests"

export async function createIdeationRequest(doc: IdeationRequest): Promise<IdeationRequest> {
  const parsed = IdeationRequestZ.parse(doc)
  const db = await getDb()
  await db
    .collection<IdeationRequest>(COLLECTION)
    .insertOne(parsed as OptionalUnlessRequiredId<IdeationRequest>)
  return parsed
}

export async function updateIdeationRequest(
  id: string,
  patch: Partial<IdeationRequest>
): Promise<IdeationRequest | null> {
  const db = await getDb()
  const result = await db.collection<IdeationRequest>(COLLECTION).findOneAndUpdate(
    { _id: id },
    { $set: { ...patch, updatedAt: new Date() } },
    { returnDocument: "after" }
  )
  return result ? IdeationRequestZ.parse(result) : null
}

export async function findIdeationRequestById(id: string): Promise<IdeationRequest | null> {
  const db = await getDb()
  const doc = await db.collection<IdeationRequest>(COLLECTION).findOne({ _id: id })
  return doc ? IdeationRequestZ.parse(doc) : null
}

export async function findIdeationRequestByHypothesisId(
  hypothesisId: string
): Promise<IdeationRequest | null> {
  const db = await getDb()
  const doc = await db.collection<IdeationRequest>(COLLECTION).findOne({ hypothesisId })
  return doc ? IdeationRequestZ.parse(doc) : null
}

export async function listIdeationRequests(
  filter: Filter<IdeationRequest> = {},
  page = 1,
  pageSize = 25
): Promise<{ items: IdeationRequest[]; total: number }> {
  const db = await getDb()
  const collection = db.collection<IdeationRequest>(COLLECTION)
  const cursor = collection
    .find(filter)
    .sort({ createdAt: -1 })
    .skip((page - 1) * pageSize)
    .limit(pageSize)

  const [items, total] = await Promise.all([cursor.toArray(), collection.countDocuments(filter)])
  return {
    items: items.map((item) => IdeationRequestZ.parse(item)),
    total
  }
}

export async function countIdeationByStatus(status: IdeationStatus): Promise<number> {
  const db = await getDb()
  return db.collection<IdeationRequest>(COLLECTION).countDocuments({ status })
}
