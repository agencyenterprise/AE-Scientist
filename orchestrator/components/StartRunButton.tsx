"use client"

import { useTransition, useState } from "react"
import { useRouter } from "next/navigation"

export function StartRunButton({
  hypothesisId,
  disabled = false,
  label = "Launch Experiment"
}: {
  hypothesisId: string
  disabled?: boolean
  label?: string
}) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  const trigger = () => {
    startTransition(async () => {
      setError(null)
      const response = await fetch(`/api/hypotheses/${hypothesisId}/runs`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "Idempotency-Key": crypto.randomUUID()
        }
      })
      if (!response.ok) {
        setError("Failed to start run")
        return
      }
      router.refresh()
    })
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={trigger}
        className="rounded border border-emerald-600/60 bg-emerald-900/40 px-3 py-1 text-xs font-semibold text-emerald-100 disabled:opacity-40"
        disabled={pending || disabled}
      >
        {label}
      </button>
      {error && <span className="text-xs text-rose-400">{error}</span>}
    </div>
  )
}
