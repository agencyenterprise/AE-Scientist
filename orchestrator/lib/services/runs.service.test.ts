import { afterEach, describe, expect, it, vi } from "vitest"

const createRunMock = vi.fn()
const findRunByIdMock = vi.fn()
const updateRunMock = vi.fn()
const queueAddMock = vi.fn()

vi.mock("../repos/runs.repo", () => ({
  createRun: createRunMock,
  findRunById: findRunByIdMock,
  updateRun: updateRunMock
}))

vi.mock("../queues/bullmq", () => ({
  getOrchestratorQueue: () => ({ add: queueAddMock })
}))

vi.mock("../state/runStateMachine", async () => {
  const actual = await vi.importActual("../state/runStateMachine")
  return {
    ...actual
  }
})

describe("runs.service", () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it("creates and enqueues run", async () => {
    const { enqueueRun } = await import("./runs.service")
    createRunMock.mockResolvedValueOnce(undefined)
    queueAddMock.mockResolvedValueOnce(undefined)
    const run = await enqueueRun("hypo-1")
    expect(run.hypothesisId).toBe("hypo-1")
    expect(run.status).toBe("QUEUED")
    expect(createRunMock).toHaveBeenCalledWith(run)
    expect(queueAddMock).toHaveBeenCalled()
  })

  it("transitions run status", async () => {
    const { transitionRun } = await import("./runs.service")
    const runId = "run-1"
    findRunByIdMock
      .mockResolvedValueOnce({ _id: runId, status: "QUEUED", hypothesisId: "h", createdAt: new Date(), updatedAt: new Date() })
      .mockResolvedValueOnce({ _id: runId, status: "SCHEDULED", hypothesisId: "h", createdAt: new Date(), updatedAt: new Date() })
    updateRunMock.mockResolvedValueOnce(undefined)

    const updated = await transitionRun(runId, "SCHEDULED")
    expect(updateRunMock).toHaveBeenCalledWith(runId, expect.objectContaining({ status: "SCHEDULED" }))
    expect(updated.status).toBe("SCHEDULED")
  })
})
