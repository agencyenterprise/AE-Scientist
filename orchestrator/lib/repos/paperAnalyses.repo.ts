import { type OptionalUnlessRequiredId } from "mongodb"
import { getDb } from "../db/mongo"
import { PaperAnalysisZ, type PaperAnalysis } from "../schemas/analysis"

const COLLECTION = "paper_analyses"

export async function createPaperAnalysis(doc: PaperAnalysis): Promise<PaperAnalysis> {
  const validated = PaperAnalysisZ.parse(doc)
  const db = await getDb()
  await db.collection<PaperAnalysis>(COLLECTION).insertOne(
    validated as OptionalUnlessRequiredId<PaperAnalysis>
  )
  return validated
}

export async function getPaperAnalysisByRunId(runId: string): Promise<PaperAnalysis | null> {
  const db = await getDb()
  const doc = await db.collection<PaperAnalysis>(COLLECTION).findOne({ runId })
  return doc ? PaperAnalysisZ.parse(doc) : null
}
