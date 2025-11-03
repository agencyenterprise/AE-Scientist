import { render, screen } from "@testing-library/react"
import { PaperAnalysisPanel } from "../PaperAnalysisPanel"
import type { PaperAnalysis } from "@/lib/schemas/analysis"

describe("PaperAnalysisPanel", () => {
  const baseAnalysis: PaperAnalysis = {
    _id: "00000000-0000-0000-0000-000000000001",
    runId: "00000000-0000-0000-0000-000000000010",
    paperId: "paper",
    quantitative: {
      quality: { score: 8 },
      overallScore: 8
    },
    qualitative: {
      tradeoffsMade: {
        example: "tradeoff"
      }
    },
    models: {
      quantitative: "gpt-test",
      qualitative: "gpt-test"
    },
    createdAt: new Date()
  }

  it("renders quantitative and qualitative sections", () => {
    render(<PaperAnalysisPanel analysis={baseAnalysis} />)
    expect(screen.getByText(/quantitative review/i)).toBeInTheDocument()
    expect(screen.getByText(/qualitative synthesis/i)).toBeInTheDocument()
  })
})
