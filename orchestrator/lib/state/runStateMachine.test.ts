import { assertTransition, isTerminal } from "./runStateMachine"
import { expect, describe, it } from "vitest"

describe("runStateMachine", () => {
  it("allows valid transitions", () => {
    expect(() => assertTransition("QUEUED", "SCHEDULED")).not.toThrow()
    expect(() => assertTransition("RUNNING", "AUTO_VALIDATING")).not.toThrow()
    expect(() => assertTransition("COMPLETED", "AUTO_VALIDATING")).not.toThrow()
    expect(() => assertTransition("COMPLETED", "AWAITING_HUMAN")).not.toThrow()
  })

  it("blocks invalid transitions", () => {
    expect(() => assertTransition("QUEUED", "RUNNING")).toThrowError(
      /Illegal run transition/
    )
    expect(() => assertTransition("AWAITING_HUMAN", "COMPLETED")).toThrowError(
      /Illegal run transition/
    )
  })

  it("detects terminal states", () => {
    expect(isTerminal("FAILED")).toBe(true)
    expect(isTerminal("RUNNING")).toBe(false)
  })
})
