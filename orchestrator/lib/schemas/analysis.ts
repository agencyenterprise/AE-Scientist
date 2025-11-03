import { z } from "zod"

const ScoreDetailZ = z.object({
  score: z.number().min(0).max(10).optional(),
  rationale: z.string().optional(),
  criteria: z.record(z.number()).optional()
})

const EfficiencyGainZ = z.object({
  tokensPerSecond: z.number().optional(),
  relativeGainVsBaseline: z.string().optional(),
  nmseExactness: z.string().optional(),
  memorySavingsEstimated: z.string().optional(),
  rationale: z.string().optional()
})

const EmpiricalSuccessZ = z.object({
  datasetsWithImprovement: z.number().int().optional(),
  datasetsTested: z.number().int().optional(),
  successRate: z.number().optional(),
  rationale: z.string().optional()
})

const ReproducibilityZ = z.object({
  codeAvailability: z.boolean().optional(),
  numericalCheckIncluded: z.boolean().optional(),
  score: z.number().optional()
})

export const QuantitativeAnalysisZ = z.object({
  quality: ScoreDetailZ.optional(),
  faithfulnessToOriginal: ScoreDetailZ.optional(),
  innovationIndex: ScoreDetailZ.optional(),
  computationalEfficiencyGain: EfficiencyGainZ.optional(),
  empiricalSuccess: EmpiricalSuccessZ.optional(),
  reliabilityOfConclusion: ScoreDetailZ.optional(),
  reproducibilityScore: ReproducibilityZ.optional(),
  overallScore: z.number().min(0).max(10).optional()
})

const ExperimentProvenZ = z.object({
  hypothesis: z.string().optional(),
  proven: z.boolean().optional(),
  evidence: z.string().optional(),
  limitations: z.string().optional()
})

export const QualitativeAnalysisZ = z.object({
  tradeoffsMade: z.record(z.string()).optional(),
  experimentProven: ExperimentProvenZ.optional(),
  conclusion: z
    .object({
      summary: z.string().optional(),
      implications: z.string().optional(),
      authorsPosition: z.string().optional()
    })
    .optional(),
  methodologicalNovelty: z.string().optional(),
  recommendations: z.array(z.string()).optional()
})

export const PaperAnalysisZ = z.object({
  _id: z.string().uuid(),
  runId: z.string().uuid(),
  paperId: z.string().min(1),
  paperTitle: z.string().optional(),
  paperUrl: z.string().url().optional(),
  quantitative: QuantitativeAnalysisZ,
  qualitative: QualitativeAnalysisZ,
  models: z.object({
    quantitative: z.string(),
    qualitative: z.string()
  }),
  createdAt: z.coerce.date(),
  seed: z.boolean().optional()
})

export type ScoreDetail = z.infer<typeof ScoreDetailZ>
export type QuantitativeAnalysis = z.infer<typeof QuantitativeAnalysisZ>
export type QualitativeAnalysis = z.infer<typeof QualitativeAnalysisZ>
export type PaperAnalysis = z.infer<typeof PaperAnalysisZ>
