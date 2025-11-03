import { render, screen } from "@testing-library/react"
import { StageProgress } from "../StageProgress"

describe("StageProgress", () => {
  it("renders stage descriptions", () => {
    render(
      <StageProgress
        stages={[
          { name: "Stage_1", progress: 1, status: "COMPLETED" },
          { name: "Stage_2", progress: 0.5, status: "RUNNING" }
        ]}
      />
    )

    expect(screen.getByText("Stage 1")).toBeInTheDocument()
    expect(screen.getByText("Stage 2")).toBeInTheDocument()
    expect(screen.getByText(/Preliminary Investigation/i)).toBeInTheDocument()
  })
})
