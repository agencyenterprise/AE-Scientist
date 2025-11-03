import { describe, expect, it } from "vitest"
import { CloudEventsEnvelopeZ, validateEventData } from "./cloudevents"

describe("CloudEventsEnvelopeZ", () => {
  it("validates a valid CloudEvents envelope", () => {
    const event = {
      specversion: "1.0",
      id: "evt-123",
      source: "runpod://pod/pod-abc",
      type: "ai.run.started",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: {
        run_id: "run-123",
        pod_id: "pod-abc",
        gpu: "A100"
      },
      extensions: {
        seq: 1
      }
    }

    const result = CloudEventsEnvelopeZ.safeParse(event)
    expect(result.success).toBe(true)
  })

  it("rejects invalid specversion", () => {
    const event = {
      specversion: "2.0",
      id: "evt-123",
      source: "test://local",
      type: "ai.run.started",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: {}
    }

    const result = CloudEventsEnvelopeZ.safeParse(event)
    expect(result.success).toBe(false)
  })

  it("requires id field", () => {
    const event = {
      specversion: "1.0",
      source: "test://local",
      type: "ai.run.started",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: {}
    }

    const result = CloudEventsEnvelopeZ.safeParse(event)
    expect(result.success).toBe(false)
  })

  it("validates ISO 8601 time format", () => {
    const event = {
      specversion: "1.0",
      id: "evt-123",
      source: "test://local",
      type: "ai.run.started",
      subject: "run/run-123",
      time: "invalid-date",
      datacontenttype: "application/json",
      data: {}
    }

    const result = CloudEventsEnvelopeZ.safeParse(event)
    expect(result.success).toBe(false)
  })

  it("allows optional extensions", () => {
    const event = {
      specversion: "1.0",
      id: "evt-123",
      source: "test://local",
      type: "ai.run.started",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: {}
    }

    const result = CloudEventsEnvelopeZ.safeParse(event)
    expect(result.success).toBe(true)
  })

  it("validates extensions.seq is positive integer", () => {
    const event = {
      specversion: "1.0",
      id: "evt-123",
      source: "test://local",
      type: "ai.run.started",
      subject: "run/run-123",
      time: "2025-10-22T19:00:00Z",
      datacontenttype: "application/json",
      data: {},
      extensions: {
        seq: -5
      }
    }

    const result = CloudEventsEnvelopeZ.safeParse(event)
    expect(result.success).toBe(false)
  })
})

describe("validateEventData", () => {
  it("validates ai.run.started data", () => {
    const data = {
      run_id: "run-123",
      pod_id: "pod-abc",
      gpu: "A100",
      region: "us-west"
    }

    expect(validateEventData("ai.run.started", data)).toBe(true)
  })

  it("validates ai.run.stage_progress data", () => {
    const data = {
      run_id: "run-123",
      stage: "Stage_1",
      progress: 0.5,
      eta_s: 300
    }

    expect(validateEventData("ai.run.stage_progress", data)).toBe(true)
  })

  it("rejects invalid stage name", () => {
    const data = {
      run_id: "run-123",
      stage: "Stage_99",
      progress: 0.5
    }

    expect(validateEventData("ai.run.stage_progress", data)).toBe(false)
  })

  it("rejects progress out of range", () => {
    const data = {
      run_id: "run-123",
      stage: "Stage_1",
      progress: 1.5
    }

    expect(validateEventData("ai.run.stage_progress", data)).toBe(false)
  })

  it("validates ai.validation.auto_completed data", () => {
    const data = {
      run_id: "run-123",
      verdict: "pass",
      scores: { overall: 0.85 },
      notes: "Looks good"
    }

    expect(validateEventData("ai.validation.auto_completed", data)).toBe(true)
  })

  it("rejects invalid verdict", () => {
    const data = {
      run_id: "run-123",
      verdict: "maybe",
      scores: {}
    }

    expect(validateEventData("ai.validation.auto_completed", data)).toBe(false)
  })

  it("validates ai.artifact.registered data", () => {
    const data = {
      run_id: "run-123",
      key: "runs/run-123/paper.pdf",
      bytes: 524288,
      sha256: "abc123",
      content_type: "application/pdf",
      kind: "paper"
    }

    expect(validateEventData("ai.artifact.registered", data)).toBe(true)
  })

  it("returns false for unknown event type", () => {
    const data = { run_id: "run-123" }
    expect(validateEventData("unknown.event.type", data)).toBe(false)
  })
})

