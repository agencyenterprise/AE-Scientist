import { afterEach, describe, expect, it, vi } from "vitest"

const getMock = vi.fn()
const setMock = vi.fn()

vi.mock("../redis/client", () => ({
  redis: {
    get: getMock,
    set: setMock
  }
}))

describe("withIdempotency", () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it("stores and returns cached result", async () => {
    const { withIdempotency } = await import("./Idempotency")
    getMock.mockResolvedValueOnce(null)
    setMock.mockResolvedValueOnce(null)
    const result = await withIdempotency("key", async () => ({ value: 42 }))
    expect(result).toEqual({ value: 42 })
    expect(setMock).toHaveBeenCalled()

    getMock.mockResolvedValueOnce(JSON.stringify({ value: 42 }))
    const cached = await withIdempotency("key", async () => ({ value: 1 }))
    expect(cached).toEqual({ value: 42 })
  })
})
