"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { Trash2, Loader2, Clock, Lightbulb } from "lucide-react"
import { StartRunButton } from "./StartRunButton"

type IdeationInfo = {
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED"
  reflections: number
  requestId?: string
  ideas?: Array<{
    Name: string
    Title: string
    [key: string]: unknown
  }>
}

type HistoryHypothesis = {
  _id: string
  title: string
  idea: string
  createdAt: string
  updatedAt?: string
  ideaJson?: Record<string, unknown>
  ideation?: IdeationInfo
  extractionStatus?: "pending" | "extracting" | "completed" | "failed"
}

type HypothesisHistoryListProps = {
  initialHypotheses: HistoryHypothesis[]
}

export function HypothesisHistoryList({ initialHypotheses }: HypothesisHistoryListProps) {
  const [items, setItems] = useState(() => initialHypotheses.slice(0, 10))
  const [hiding, setHiding] = useState<string | null>(null)

  const visibleItems = items

  const handleHide = async (id: string) => {
    if (hiding) return
    setHiding(id)
    try {
      const response = await fetch(`/api/hypotheses/${id}/hide`, { method: "POST" })
      if (!response.ok) {
        const data = await response.json().catch(() => null)
        const message = data?.error || "Failed to hide hypothesis"
        alert(message)
      } else {
        setItems((prev) => prev.filter((hypothesis) => hypothesis._id !== id))
      }
    } catch (error) {
      console.error("Hide hypothesis request failed", error)
      alert("Failed to hide hypothesis")
    } finally {
      setHiding(null)
    }
  }

  if (visibleItems.length === 0) {
    return null
  }

  return (
    <section className="rounded-[2.4rem] border border-slate-800/70 bg-slate-950/70 p-6 shadow-[0_40px_120px_-70px_rgba(14,165,233,0.8)]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-sky-200">
          <Lightbulb className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-[0.35em]">Hypothesis history</span>
        </div>
        <span className="text-[11px] uppercase tracking-[0.3em] text-slate-500">
          Last {visibleItems.length} entries
        </span>
      </div>
      <div className="mt-6 grid gap-4">
        {visibleItems.map((hypothesis) => {
          const createdAt = new Date(hypothesis.createdAt)
          const relativeCreated = formatDistanceToNow(createdAt, { addSuffix: true })
          const launchedAt = hypothesis.updatedAt ? new Date(hypothesis.updatedAt) : createdAt
          const ideationStatus = hypothesis.ideation?.status
          const primaryIdea = hypothesis.ideation?.ideas?.[0]
          const runDisabled =
            !hypothesis.ideaJson || (!!ideationStatus && ideationStatus !== "COMPLETED")
          const hasExperiments = Boolean(hypothesis.updatedAt)

          const hideButtonDisabled = hiding === hypothesis._id

          return (
            <article
              key={hypothesis._id}
              className="group relative overflow-hidden rounded-[1.75rem] border border-slate-800/70 bg-slate-950/70 p-5 transition hover:border-sky-500/60"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold leading-snug text-slate-100 line-clamp-2 break-words">
                      {hypothesis.title}
                    </p>
                    {ideationStatus === "RUNNING" && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-200">
                        ideation running
                      </span>
                    )}
                    {ideationStatus === "QUEUED" && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-200">
                        ideation queued
                      </span>
                    )}
                    {ideationStatus === "FAILED" && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-200">
                        ideation failed
                      </span>
                    )}
                  </div>

                  {primaryIdea ? (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
                        Ideation highlight
                      </p>
                      <p className="text-sm font-semibold text-sky-200">{primaryIdea.Title}</p>
                      <p className="line-clamp-4 whitespace-pre-line text-xs leading-relaxed text-slate-300">
                        {typeof primaryIdea["Short Hypothesis"] === "string"
                          ? primaryIdea["Short Hypothesis"]
                          : hypothesis.idea}
                      </p>
                    </div>
                  ) : (
                    <p className="line-clamp-4 whitespace-pre-line text-xs leading-relaxed text-slate-400">
                      {hypothesis.idea}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-slate-500">
                    <span className="inline-flex items-center gap-1 rounded-full border border-slate-800/80 bg-slate-900/70 px-3 py-1 font-semibold">
                      <Clock className="h-3 w-3 text-slate-400" />
                      {relativeCreated}
                    </span>
                    {launchedAt && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-slate-800/60 bg-slate-900/60 px-3 py-1 font-medium text-slate-200">
                        launched {launchedAt.toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-col items-end gap-2">
                  <StartRunButton
                    hypothesisId={hypothesis._id}
                    disabled={runDisabled}
                    label={
                      runDisabled
                        ? "Waiting on ideation"
                        : hasExperiments
                          ? "Relaunch experiment"
                          : "Launch experiment"
                    }
                  />
                  <button
                    type="button"
                    onClick={() => handleHide(hypothesis._id)}
                    disabled={hideButtonDisabled}
                    className="rounded-full border border-slate-700 bg-slate-900/60 p-2 text-slate-400 transition hover:border-rose-500/60 hover:text-rose-200 disabled:opacity-40"
                    aria-label="Hide hypothesis"
                  >
                    {hideButtonDisabled ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            </article>
          )
        })}
      </div>

      <p className="mt-6 text-[11px] uppercase tracking-[0.3em] text-slate-500">
        Hidden hypotheses can still be found in your database but will no longer appear in quick-start lists.
      </p>
    </section>
  )
}
