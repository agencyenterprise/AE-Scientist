"use client"

import { useRouter } from "next/navigation"
import type { KeyboardEvent } from "react"
import type { Run } from "@/lib/schemas/run"
import type { Hypothesis } from "@/lib/schemas/hypothesis"
import type { Validation } from "@/lib/schemas/validation"
import { StatusBadge } from "@/components/StatusBadge"
import { ValidationSummary } from "@/components/ValidationSummary"
import { ArrowUpRight } from "lucide-react"

export function ValidationQueueCard({
  run,
  hypothesis,
  validations
}: {
  run: Run
  hypothesis?: Hypothesis
  validations: Validation[]
}) {
  const router = useRouter()
  const auto = validations.find((validation) => validation.kind === "auto")
  const human = validations.find((validation) => validation.kind === "human")
  const runHref = `/runs/${run._id}`

  const navigateToRun = () => {
    router.push(runHref)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      navigateToRun()
    }
  }

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={navigateToRun}
      onKeyDown={handleKeyDown}
      className="group relative cursor-pointer rounded-2xl border border-slate-800 bg-slate-900/40 p-6 transition hover:-translate-y-0.5 hover:border-sky-500/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60"
      aria-label={`Open run ${run._id}`}
    >
      <div className="absolute inset-y-0 left-0 w-1 rounded-l-2xl bg-gradient-to-b from-sky-500/70 via-blue-500/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      <div className="relative flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <span>Run {run._id}</span>
            <ArrowUpRight className="h-4 w-4 text-sky-300" aria-hidden="true" />
          </div>
          <p className="text-sm text-slate-300">{hypothesis?.title ?? "Unknown hypothesis"}</p>
          <p className="text-xs text-slate-500">Click to inspect full experiment details</p>
        </div>
        <StatusBadge status={run.status} />
      </div>
      <div className="relative mt-4">
        <ValidationSummary auto={auto} human={human} />
      </div>
    </article>
  )
}
