"use client"

import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"
import type { RunStatus } from "@/lib/state/constants"

export function RunActions({ 
  runId, 
  status,
  canCancel,
  canRetryWriteup 
}: { 
  runId: string
  status: RunStatus
  canCancel: boolean
  canRetryWriteup?: boolean
}) {
  const router = useRouter()
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)

  const cancel = () => {
    if (!confirm("Cancel this run?")) return
    startTransition(async () => {
      setError(null)
      setSuccess(null)
      const response = await fetch(`/api/runs/${runId}/cancel`, {
        method: "POST"
      })
      if (!response.ok) {
        setError("Failed to cancel run")
        return
      }
      router.refresh()
    })
  }

  const retryWriteup = () => {
    if (!confirm("Retry paper generation for this run? A pod worker will pick it up and progress will appear in live logs below.")) return
    startTransition(async () => {
      setError(null)
      setSuccess(null)
      const response = await fetch(`/api/runs/${runId}/retry-writeup`, {
        method: "POST"
      })
      if (!response.ok) {
        const data = await response.json()
        setError(data.error || "Failed to start writeup retry")
        return
      }
      const data = await response.json()
      setSuccess("✅ " + data.message)
      setTimeout(() => {
        setSuccess(null)
        router.refresh()
      }, 5000)
    })
  }

  if (!canCancel && !canRetryWriteup) {
    return null
  }

  // For COMPLETED runs with retry option, show in dropdown menu
  // For FAILED runs, show retry button prominently
  const showRetryInMenu = canRetryWriteup && status === "COMPLETED"
  const showRetryProminent = canRetryWriteup && status === "FAILED"

  return (
    <div className="flex items-center gap-3">
      {canCancel && (
        <button
          className="rounded border border-rose-600/60 bg-rose-900/40 px-4 py-2 text-sm font-semibold text-rose-100 disabled:opacity-40"
          onClick={cancel}
          disabled={pending}
        >
          Cancel Run
        </button>
      )}
      {showRetryProminent && (
        <button
          className="rounded border border-blue-600/60 bg-blue-900/40 px-4 py-2 text-sm font-semibold text-blue-100 disabled:opacity-40 hover:bg-blue-900/60"
          onClick={retryWriteup}
          disabled={pending}
        >
          Retry Paper Generation
        </button>
      )}
      {showRetryInMenu && (
        <div className="relative">
          <button
            className="rounded border border-slate-700 bg-slate-800/40 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800/60 disabled:opacity-40"
            onClick={() => setMenuOpen(!menuOpen)}
            disabled={pending}
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
            </svg>
          </button>
          {menuOpen && (
            <div className="absolute right-0 z-10 mt-2 w-56 rounded-md border border-slate-700 bg-slate-800 shadow-lg">
              <div className="py-1">
                <button
                  className="block w-full px-4 py-2 text-left text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-40"
                  onClick={() => {
                    setMenuOpen(false)
                    retryWriteup()
                  }}
                  disabled={pending}
                >
                  Retry Paper Generation
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {error && <span className="text-sm text-rose-400">{error}</span>}
      {success && <span className="text-sm text-emerald-400">{success}</span>}
    </div>
  )
}
