import { render, screen } from "@testing-library/react"
import { RunTable } from "../RunTable"
import type { Run } from "@/lib/schemas/run"

describe("RunTable", () => {
  const baseRun: Run = {
    _id: "00000000-0000-0000-0000-000000000001",
    hypothesisId: "00000000-0000-0000-0000-000000000010",
    status: "RUNNING",
    currentStage: { name: "Stage_2", progress: 0.5 },
    createdAt: new Date("2024-01-01T00:00:00Z"),
    updatedAt: new Date("2024-01-01T01:00:00Z"),
    seed: true
  }

  it("renders run data", () => {
    render(
      <RunTable
        rows={[
          {
            run: baseRun,
            hypothesisTitle: "Hypothesis Alpha"
          }
        ]}
      />
    )

    expect(screen.getByText("Hypothesis Alpha")).toBeInTheDocument()
    expect(screen.getByText(baseRun._id)).toBeInTheDocument()
    expect(screen.getByText(/view/i)).toHaveAttribute("href", `/runs/${baseRun._id}`)
  })

  it("renders empty state", () => {
    render(<RunTable rows={[]} />)
    expect(screen.getByText(/no runs found/i)).toBeInTheDocument()
  })
})
