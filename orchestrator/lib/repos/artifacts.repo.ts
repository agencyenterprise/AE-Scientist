import { type OptionalUnlessRequiredId } from "mongodb"
import { getDb } from "../db/mongo"
import { ArtifactZ, type Artifact } from "../schemas/artifact"

const COLLECTION = "artifacts"

export async function createArtifact(artifact: Artifact): Promise<Artifact> {
  const doc = ArtifactZ.parse(artifact)
  const db = await getDb()
  await db.collection<Artifact>(COLLECTION).insertOne(
    doc as OptionalUnlessRequiredId<Artifact>
  )
  return doc
}

export async function listArtifactsForRun(runId: string): Promise<Artifact[]> {
  const db = await getDb()
  const docs = await db
    .collection<Artifact>(COLLECTION)
    .find({ runId })
    .sort({ createdAt: -1 })
    .toArray()
  return docs.map((doc) => ArtifactZ.parse(doc))
}
