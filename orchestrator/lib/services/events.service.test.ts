import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { CloudEventsEnvelope } from "../schemas/cloudevents"

const mockFindRunById = vi.fn()
const mockUpdateRun = vi.fn()
const mockCreateStage = vi.fn()
const mockUpdateStage = vi.fn()
const mockCreateValidation = vi.fn()
const mockCreateArtifact = vi.fn()
const mockCreateEvent = vi.fn()

vi.mock("../repos/runs.repo", () => ({
  findRunById: mockFindRunById,
  updateRun: mockUpdateRun
}))

vi.mock("../repos/stages.repo", () => ({
  createStage: mockCreateStage,
  updateStage: mockUpdateStage
}))

vi.mock("../repos/validations.repo", () => ({
  createValidation: mockCreateValidation
}))

vi.mock("../repos/artifacts.repo", () => ({
  createArtifact: mockCreateArtifact
}))

vi.mock("../repos/events.repo", () => ({
  createEvent: mockCreateEvent
}))

describe("processEvent", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFindRunById.mockResolvedValue({
      _id: "run-123",
      hypothesisId: "hyp-123",
      status: "RUNNING",
      lastEventSeq: 0
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it("creates event record in database", async () => {
    const { processEvent } = await import("./events.service")
    
    const event: CloudEventsEnvelope = {
      specversion: "1.0",
      id: "evt-123",
      source: "test://local",
      type: "ai.run.heartbeat",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: { run_id: "run-123", gpu_util: 0.75 },
      extensions: { seq: 1 }
    }

    await processEvent(event)

    expect(mockCreateEvent).toHaveBeenCalledWith({
      _id: "evt-123",
      runId: "run-123",
      type: "ai.run.heartbeat",
      data: { run_id: "run-123", gpu_util: 0.75 },
      source: "test://local",
      timestamp: expect.any(Date),
      seq: 1
    })
  })

  it("updates lastEventSeq after processing", async () => {
    const { processEvent } = await import("./events.service")
    
    const event: CloudEventsEnvelope = {
      specversion: "1.0",
      id: "evt-124",
      source: "test://local",
      type: "ai.run.heartbeat",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: { run_id: "run-123" },
      extensions: { seq: 5 }
    }

    await processEvent(event)

    expect(mockUpdateRun).toHaveBeenCalledWith("run-123", { lastEventSeq: 5 })
  })

  it("ignores out-of-order events", async () => {
    const { processEvent } = await import("./events.service")
    
    mockFindRunById.mockResolvedValue({
      _id: "run-123",
      status: "RUNNING",
      lastEventSeq: 10
    })

    const event: CloudEventsEnvelope = {
      specversion: "1.0",
      id: "evt-old",
      source: "test://local",
      type: "ai.run.heartbeat",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: { run_id: "run-123" },
      extensions: { seq: 5 }
    }

    await processEvent(event)

    expect(mockCreateEvent).not.toHaveBeenCalled()
  })

  it("handles stage started event", async () => {
    const { processEvent } = await import("./events.service")
    
    const event: CloudEventsEnvelope = {
      specversion: "1.0",
      id: "evt-stage",
      source: "test://local",
      type: "ai.run.stage_started",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: { run_id: "run-123", stage: "Stage_1", desc: "Preliminary Investigation" },
      extensions: { seq: 2 }
    }

    await processEvent(event)

    expect(mockCreateStage).toHaveBeenCalledWith({
      _id: "run-123-Stage_1",
      runId: "run-123",
      index: 0,
      name: "Stage_1",
      status: "RUNNING",
      startedAt: expect.any(Date),
      progress: 0
    })

    expect(mockUpdateRun).toHaveBeenCalledWith("run-123", {
      currentStage: {
        name: "Stage_1",
        progress: 0
      }
    })
  })

  it("handles stage progress event", async () => {
    const { processEvent } = await import("./events.service")
    
    const event: CloudEventsEnvelope = {
      specversion: "1.0",
      id: "evt-progress",
      source: "test://local",
      type: "ai.run.stage_progress",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: { run_id: "run-123", stage: "Stage_1", progress: 0.5, eta_s: 300 },
      extensions: { seq: 3 }
    }

    await processEvent(event)

    expect(mockUpdateStage).toHaveBeenCalledWith("run-123-Stage_1", {
      progress: 0.5
    })

    expect(mockUpdateRun).toHaveBeenCalledWith("run-123", {
      currentStage: {
        name: "Stage_1",
        progress: 0.5
      }
    })
  })

  it("handles validation completed event", async () => {
    const { processEvent } = await import("./events.service")
    
    const event: CloudEventsEnvelope = {
      specversion: "1.0",
      id: "evt-val",
      source: "test://local",
      type: "ai.validation.auto_completed",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: {
        run_id: "run-123",
        verdict: "pass",
        scores: { overall: 0.85 },
        notes: "Looks good",
        model: "gpt-4o"
      },
      extensions: { seq: 10 }
    }

    await processEvent(event)

    expect(mockCreateValidation).toHaveBeenCalledWith({
      _id: expect.stringContaining("run-123-auto-"),
      runId: "run-123",
      kind: "auto",
      verdict: "pass",
      rubric: { overall: 0.85 },
      notes: "Looks good",
      createdAt: expect.any(Date),
      createdBy: "gpt-4o"
    })
  })

  it("handles artifact registered event", async () => {
    const { processEvent } = await import("./events.service")
    
    const event: CloudEventsEnvelope = {
      specversion: "1.0",
      id: "evt-artifact",
      source: "test://local",
      type: "ai.artifact.registered",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: {
        run_id: "run-123",
        key: "runs/run-123/paper.pdf",
        bytes: 524288,
        sha256: "abc123",
        content_type: "application/pdf",
        kind: "paper"
      },
      extensions: { seq: 15 }
    }

    await processEvent(event)

    expect(mockCreateArtifact).toHaveBeenCalledWith({
      _id: expect.stringContaining("run-123-paper-"),
      runId: "run-123",
      key: "runs/run-123/paper.pdf",
      kind: "paper",
      contentType: "application/pdf",
      size: 524288,
      createdAt: expect.any(Date)
    })
  })
})

