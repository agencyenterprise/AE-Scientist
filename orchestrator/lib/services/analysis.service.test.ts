import { describe, expect, it, vi, beforeEach } from "vitest"

const mockCreate = vi.fn()
const mockGet = vi.fn()
const mockFindRun = vi.fn()

vi.mock("../repos/paperAnalyses.repo", () => ({
  createPaperAnalysis: mockCreate,
  getPaperAnalysisByRunId: mockGet
}))

vi.mock("../repos/runs.repo", () => ({
  findRunById: mockFindRun
}))

describe("analysis.service", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("generates and persists analysis", async () => {
    const { generatePaperAnalysis } = await import("./analysis.service")
    const runId = "00000000-0000-0000-0000-000000000001"
    const hypothesisId = "00000000-0000-0000-0000-000000000002"
    mockFindRun.mockResolvedValueOnce({
      _id: runId,
      hypothesisId: hypothesisId,
      status: "RUNNING",
      createdAt: new Date(),
      updatedAt: new Date()
    })
    mockGet.mockResolvedValueOnce(null)
    mockCreate.mockImplementation(async (doc) => doc)

    const result = await generatePaperAnalysis(
      {
        runId: runId,
        paperId: "paper",
        paperContent: "A".repeat(200)
      },
      {
        async generateQuantitative() {
          return {
            model: "gpt-quant",
            result: {
              quality: { score: 8 },
              overallScore: 8
            }
          }
        },
        async generateQualitative() {
          return {
            model: "gpt-qual",
            result: {
              tradeoffsMade: {
                example: "tradeoff"
              }
            }
          }
        }
      }
    )

    expect(result.models.quantitative).toBe("gpt-quant")
    expect(result.quantitative.overallScore).toBe(8)
    expect(mockCreate).toHaveBeenCalled()
  })

  it("returns cached analysis when it exists", async () => {
    const { generatePaperAnalysis } = await import("./analysis.service")
    const runId = "00000000-0000-0000-0000-000000000001"
    const hypothesisId = "00000000-0000-0000-0000-000000000002"
    const analysisId = "00000000-0000-0000-0000-000000000003"
    mockFindRun.mockResolvedValue({
      _id: runId,
      hypothesisId: hypothesisId,
      status: "RUNNING",
      createdAt: new Date(),
      updatedAt: new Date()
    })
    mockGet.mockResolvedValueOnce({
      _id: analysisId,
      runId: runId
    })

    const existing = await generatePaperAnalysis(
      {
        runId: runId,
        paperId: "paper",
        paperContent: "A".repeat(200)
      },
      {
        generateQuantitative: vi.fn(),
        generateQualitative: vi.fn()
      } as never
    )

    expect(existing).toEqual({ _id: analysisId, runId: runId })
    expect(mockCreate).not.toHaveBeenCalled()
  })
})
