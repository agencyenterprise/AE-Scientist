import { randomUUID } from "node:crypto"
import { createPaperAnalysis, getPaperAnalysisByRunId } from "@/lib/repos/paperAnalyses.repo"
import { findRunById } from "@/lib/repos/runs.repo"
import {
  PaperAnalysisZ,
  type PaperAnalysis,
  QuantitativeAnalysisZ,
  type QuantitativeAnalysis,
  QualitativeAnalysisZ,
  type QualitativeAnalysis
} from "@/lib/schemas/analysis"
import { getEnv } from "@/lib/config/env"
import { callStructuredJson } from "@/lib/llm/openaiClient"

export type PaperAnalysisInput = {
  runId: string
  paperId: string
  paperTitle?: string
  paperUrl?: string
  paperContent: string
}

export interface PaperAnalysisLLM {
  generateQuantitative(input: LlmContext): Promise<{ result: QuantitativeAnalysis; model: string }>
  generateQualitative(input: LlmContext): Promise<{ result: QualitativeAnalysis; model: string }>
}

type LlmContext = {
  paperId: string
  paperTitle?: string
  paperUrl?: string
  paperContent: string
}

const defaultLlm: PaperAnalysisLLM = {
  async generateQuantitative({ paperContent, paperTitle, paperId }) {
    const env = getEnv()
    const response = await callStructuredJson({
      name: "quantitativeAnalysis",
      model: env.OPENAI_MODEL_QUANT ?? env.OPENAI_MODEL_QUAL ?? "gpt-4.1-mini",
      prompt: buildQuantPrompt({ paperContent, paperTitle, paperId }),
      schema: quantitativeSchema
    })
    const parsed = QuantitativeAnalysisZ.parse(response.content)
    return { result: parsed, model: response.model }
  },
  async generateQualitative({ paperContent, paperTitle, paperId }) {
    const env = getEnv()
    const response = await callStructuredJson({
      name: "qualitativeAnalysis",
      model: env.OPENAI_MODEL_QUAL ?? env.OPENAI_MODEL_QUANT ?? "gpt-4.1-mini",
      prompt: buildQualPrompt({ paperContent, paperTitle, paperId }),
      schema: qualitativeSchema
    })
    const parsed = QualitativeAnalysisZ.parse(response.content)
    return { result: parsed, model: response.model }
  }
}

export async function generatePaperAnalysis(
  input: PaperAnalysisInput,
  llm: PaperAnalysisLLM = defaultLlm
): Promise<PaperAnalysis> {
  const run = await findRunById(input.runId)
  if (!run) {
    throw new Error(`Run ${input.runId} not found`)
  }

  const existing = await getPaperAnalysisByRunId(input.runId)
  if (existing) {
    return existing
  }

  const context = {
    paperContent: input.paperContent,
    paperTitle: input.paperTitle,
    paperId: input.paperId,
    paperUrl: input.paperUrl
  }

  const [quant, qual] = await Promise.all([
    llm.generateQuantitative(context),
    llm.generateQualitative(context)
  ])

  const analysis: PaperAnalysis = PaperAnalysisZ.parse({
    _id: randomUUID(),
    runId: input.runId,
    paperId: input.paperId,
    paperTitle: input.paperTitle,
    paperUrl: input.paperUrl,
    quantitative: quant.result,
    qualitative: qual.result,
    models: {
      quantitative: quant.model,
      qualitative: qual.model
    },
    createdAt: new Date()
  })

  await createPaperAnalysis(analysis)
  return analysis
}

export async function getPaperAnalysis(runId: string) {
  return getPaperAnalysisByRunId(runId)
}

const scoreSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    score: { type: "number" },
    rationale: { type: "string" },
    criteria: {
      type: "object",
      additionalProperties: { type: "number" }
    }
  }
}

const quantitativeSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    quality: scoreSchema,
    faithfulnessToOriginal: scoreSchema,
    innovationIndex: scoreSchema,
    computationalEfficiencyGain: {
      type: "object",
      additionalProperties: false,
      properties: {
        tokensPerSecond: { type: "number" },
        relativeGainVsBaseline: { type: "string" },
        nmseExactness: { type: "string" },
        memorySavingsEstimated: { type: "string" },
        rationale: { type: "string" }
      }
    },
    empiricalSuccess: {
      type: "object",
      additionalProperties: false,
      properties: {
        datasetsWithImprovement: { type: "number" },
        datasetsTested: { type: "number" },
        successRate: { type: "number" },
        rationale: { type: "string" }
      }
    },
    reliabilityOfConclusion: scoreSchema,
    reproducibilityScore: {
      type: "object",
      additionalProperties: false,
      properties: {
        codeAvailability: { type: "boolean" },
        numericalCheckIncluded: { type: "boolean" },
        score: { type: "number" }
      }
    },
    overallScore: { type: "number" }
  }
}

const qualitativeSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    tradeoffsMade: {
      type: "object",
      additionalProperties: { type: "string" }
    },
    experimentProven: {
      type: "object",
      additionalProperties: false,
      properties: {
        hypothesis: { type: "string" },
        proven: { type: "boolean" },
        evidence: { type: "string" },
        limitations: { type: "string" }
      }
    },
    conclusion: {
      type: "object",
      additionalProperties: false,
      properties: {
        summary: { type: "string" },
        implications: { type: "string" },
        authorsPosition: { type: "string" }
      }
    },
    methodologicalNovelty: { type: "string" },
    recommendations: {
      type: "array",
      items: { type: "string" }
    }
  }
}

function buildQuantPrompt({ paperContent, paperTitle, paperId }: LlmContext) {
  return `You are an expert research reviewer. Analyse the paper with ID ${paperId} titled "${paperTitle ?? "(untitled)"}".
Return a JSON object that matches the quantitative schema provided, filling scores from 0-10 when appropriate.
Paper content:
---
${paperContent}
---
Respond with JSON only.`
}

function buildQualPrompt({ paperContent, paperTitle, paperId }: LlmContext) {
  return `You are an expert research reviewer. Provide a qualitative synthesis for paper ID ${paperId} titled "${paperTitle ?? "(untitled)"}".
Follow the schema for trade-offs, experiment conclusions, and recommendations.
Paper content:
---
${paperContent}
---
Respond with JSON only.`
}
