"use client"

import { useState, useTransition } from "react"
import { useRouter } from "next/navigation"
import { type Run } from "@/lib/schemas/run"

interface ErrorDisplayProps {
  run: Run
}

export function ErrorDisplay({ run }: ErrorDisplayProps) {
  const router = useRouter()
  const [showTraceback, setShowTraceback] = useState(false)
  const [traceback, setTraceback] = useState<string | null>(run.errorTraceback ?? null)
  const [loadingTraceback, setLoadingTraceback] = useState(false)
  const [pending, startTransition] = useTransition()
  const [retryError, setRetryError] = useState<string | null>(null)

  if (run.status !== "FAILED" || !run.errorMessage) {
    return null
  }

  const handleViewTraceback = async () => {
    if (traceback) {
      setShowTraceback(true)
      return
    }

    setLoadingTraceback(true)
    try {
      const response = await fetch(`/api/runs/${run._id}/events?type=ai.run.failed`)
      if (!response.ok) {
        throw new Error("Failed to fetch traceback")
      }
      
      const data = await response.json()
      const failedEvent = data.items?.find(
        (e: any) => e.type === "ai.run.failed" || e.type === "run.failed"
      )
      
      if (failedEvent?.data?.traceback) {
        setTraceback(failedEvent.data.traceback)
        setShowTraceback(true)
      } else if (run.errorTraceback) {
        setTraceback(run.errorTraceback)
        setShowTraceback(true)
      } else {
        setTraceback("No traceback available")
        setShowTraceback(true)
      }
    } catch (error) {
      console.error("Failed to fetch traceback:", error)
      setTraceback("Failed to load traceback")
      setShowTraceback(true)
    } finally {
      setLoadingTraceback(false)
    }
  }

  const handleRetry = () => {
    startTransition(async () => {
      setRetryError(null)
      try {
        const response = await fetch(`/api/hypotheses/${run.hypothesisId}/runs`, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "Idempotency-Key": crypto.randomUUID()
          }
        })
        
        if (!response.ok) {
          throw new Error("Failed to start retry")
        }
        
        const newRun = await response.json()
        router.push(`/runs/${newRun._id}`)
        router.refresh()
      } catch (error) {
        setRetryError("Failed to retry run")
      }
    })
  }

  return (
    <>
      <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-6">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-red-300">Experiment Failed</h3>
            
            <div className="mt-2">
              <p className="text-xs font-medium text-red-400">{run.errorType}</p>
              <p className="mt-1 text-sm text-red-200">{run.errorMessage}</p>
            </div>
            
            {run.failedAt && (
              <p className="mt-3 text-xs text-slate-400">
                Failed at {new Date(run.failedAt).toLocaleString()}
              </p>
            )}
            
            <div className="mt-4 flex gap-3">
              <button 
                onClick={handleViewTraceback}
                disabled={loadingTraceback}
                className="rounded bg-red-600/20 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-600/30 disabled:opacity-40"
              >
                {loadingTraceback ? "Loading..." : "View Full Traceback"}
              </button>
              <button 
                onClick={handleRetry}
                disabled={pending}
                className="rounded bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 disabled:opacity-40"
              >
                {pending ? "Starting..." : "Retry Run"}
              </button>
            </div>
            
            {retryError && (
              <p className="mt-2 text-xs text-red-400">{retryError}</p>
            )}
          </div>
        </div>
      </div>

      {showTraceback && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-8"
          onClick={() => setShowTraceback(false)}
        >
          <div 
            className="relative w-full max-w-4xl max-h-[80vh] overflow-hidden rounded-lg bg-slate-900 border border-slate-700"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 flex items-center justify-between border-b border-slate-700 bg-slate-900 px-6 py-4">
              <h3 className="text-lg font-semibold text-slate-200">Full Traceback</h3>
              <button
                className="rounded-full p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                onClick={() => setShowTraceback(false)}
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="overflow-y-auto p-6" style={{ maxHeight: "calc(80vh - 4rem)" }}>
              <pre className="text-xs text-red-300 whitespace-pre-wrap font-mono bg-slate-950 p-4 rounded border border-slate-800">
                {traceback || "Loading..."}
              </pre>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
