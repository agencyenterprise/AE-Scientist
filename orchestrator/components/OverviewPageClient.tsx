"use client"

import { useQuery } from "@tanstack/react-query"
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react"
import Link from "next/link"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { StatusBadge } from "@/components/StatusBadge"
import { RUN_STATUSES, type RunStatus } from "@/lib/state/constants"
import type { Run } from "@/lib/schemas/run"
import type { Hypothesis } from "@/lib/schemas/hypothesis"
import { formatDistanceToNow } from "date-fns"
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Clock,
  Cpu,
  FlaskConical,
  Rocket,
  Sparkles,
  TrendingUp
} from "lucide-react"
import { cn } from "@/lib/utils/cn"

const RUNS_PAGE_SIZE = 15

type OverviewData = {
  counts: Record<RunStatus, number>
  queueStatus: { totalSlots: number; running: number; queued: number }
  latestRuns: Array<{ run: Run; hypothesis?: Hypothesis }>
  topHypotheses: Array<{ hypothesis: Hypothesis; runCount: number; lastRunAt: Date | string }>
  hypotheses: Array<{ _id: string; title: string }>
}

type RunsResponse = {
  items: Run[]
  total: number
  page: number
  pageSize: number
}

function logChanges(prev: OverviewData | undefined, current: OverviewData) {
  if (!prev) {
    console.log(
      `[Overview] Queue: ${current.queueStatus.queued}Q/${current.queueStatus.running}R, Latest runs: ${current.latestRuns.length}`
    )
    return
  }

  const changes: string[] = []

  if (prev.queueStatus.queued !== current.queueStatus.queued) {
    changes.push(`Queued: ${prev.queueStatus.queued} → ${current.queueStatus.queued}`)
  }

  if (prev.queueStatus.running !== current.queueStatus.running) {
    changes.push(`Running: ${prev.queueStatus.running} → ${current.queueStatus.running}`)
  }

  const statusKeys: RunStatus[] = ["QUEUED", "RUNNING", "AUTO_VALIDATING", "AWAITING_HUMAN", "FAILED"]
  statusKeys.forEach((status) => {
    if (prev.counts[status] !== current.counts[status]) {
      changes.push(`${status}: ${prev.counts[status]} → ${current.counts[status]}`)
    }
  })

  if (changes.length > 0) {
    console.log(`[Overview] ${changes.join(" | ")}`)
  }
}

export function OverviewPageClient({ initialData }: { initialData: OverviewData }) {
  const prevDataRef = useRef<OverviewData | undefined>(undefined)
  const router = useRouter()
  const searchParams = useSearchParams()
  const pathname = usePathname()

  const { data } = useQuery({
    queryKey: ["overview"],
    queryFn: async () => {
      const res = await fetch("/api/overview")
      if (!res.ok) throw new Error("Failed to fetch overview")
      return res.json() as Promise<OverviewData>
    },
    initialData,
    refetchInterval: 5000,
    refetchOnWindowFocus: true
  })

  useEffect(() => {
    logChanges(prevDataRef.current, data)
    prevDataRef.current = data
  }, [data])

  const statusFilter = searchParams.get("status") ?? ""
  const hypothesisFilter = searchParams.get("hypothesisId") ?? ""
  const runsPage = Math.max(1, Number.parseInt(searchParams.get("page") ?? "1", 10) || 1)

  const setQueryParams = (updates: Record<string, string | undefined>) => {
    const params = new URLSearchParams(searchParams)
    Object.entries(updates).forEach(([key, value]) => {
      if (value && value.length > 0) {
        params.set(key, value)
      } else {
        params.delete(key)
      }
    })
    const query = params.toString()
    const hash = "#runs-board"
    router.replace(query ? `${pathname}?${query}${hash}` : `${pathname}${hash}`)
  }

  const { data: runsData, isFetching: runsLoading } = useQuery({
    queryKey: ["overview-runs", statusFilter, hypothesisFilter, runsPage],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set("page", runsPage.toString())
      params.set("pageSize", RUNS_PAGE_SIZE.toString())
      if (statusFilter) params.set("status", statusFilter)
      if (hypothesisFilter) params.set("hypothesisId", hypothesisFilter)

      const res = await fetch(`/api/runs?${params.toString()}`)
      if (!res.ok) throw new Error("Failed to fetch runs")
      return res.json() as Promise<RunsResponse>
    },
    keepPreviousData: true
  })

  const hypothesisMap = useMemo(() => {
    const map = new Map<string, string>()
    for (const hypothesis of data.hypotheses) {
      map.set(hypothesis._id, hypothesis.title)
    }
    return map
  }, [data.hypotheses])

  const runRows = useMemo(
    () =>
      (runsData?.items ?? []).map((run) => ({
        run,
        hypothesisTitle: hypothesisMap.get(run.hypothesisId)
      })),
    [runsData?.items, hypothesisMap]
  )

  const totalPages = runsData ? Math.max(1, Math.ceil(runsData.total / RUNS_PAGE_SIZE)) : 1

  const goToPage = (targetPage: number) => {
    const clamped = Math.max(1, Math.min(targetPage, totalPages))
    setQueryParams({ page: clamped === 1 ? undefined : String(clamped) })
  }

  const queued =
    (data.counts.QUEUED ?? 0) + (data.counts.SCHEDULED ?? 0) + (data.counts.STARTING ?? 0)
  const running = data.counts.RUNNING ?? 0
  const validating = (data.counts.AUTO_VALIDATING ?? 0) + (data.counts.AWAITING_HUMAN ?? 0)
  const completed = (data.counts.COMPLETED ?? 0) + (data.counts.HUMAN_VALIDATED ?? 0)
  const failed = data.counts.FAILED ?? 0
  const canceled = data.counts.CANCELED ?? 0

  const activeExperiments = running + validating
  const availablePods = Math.max(0, data.queueStatus.totalSlots - data.queueStatus.running)
  const latestRuns = data.latestRuns.slice(0, 6)
  const experimentsInPipeline = queued + running
  const estimatedHours = experimentsInPipeline > 0
    ? Math.ceil(experimentsInPipeline / Math.max(1, data.queueStatus.totalSlots)) * 6
    : 0

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-12">
      <section className="relative overflow-hidden rounded-[2.75rem] border border-slate-800/70 bg-slate-950/70 px-8 py-12 shadow-[0_60px_150px_-80px_rgba(56,189,248,0.9)] sm:px-12">
        <div className="pointer-events-none absolute -left-1/3 top-1/2 h-[480px] w-[480px] -translate-y-1/2 rounded-full bg-sky-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -right-1/4 top-10 h-[400px] w-[400px] rounded-full bg-indigo-500/20 blur-[120px]" />

        <div className="relative flex flex-col gap-10">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-2xl">
              <span className="inline-flex items-center gap-2 rounded-full border border-sky-500/40 bg-sky-500/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-sky-200">
                <Sparkles className="h-3.5 w-3.5" />
                Pipeline Pulse
              </span>
              <h1 className="mt-4 text-balance text-4xl font-semibold text-white sm:text-5xl">
                A panoramic view of every experiment in flight
              </h1>
              <p className="mt-4 text-base text-slate-300 sm:text-lg">
                Track compute utilization, queue depth, and live progress. The overview refreshes automatically so you always have the latest pulse on your AI Scientist.
              </p>
            </div>

            <div className="grid w-full max-w-sm gap-4 rounded-3xl border border-slate-800/70 bg-slate-950/70 p-6 text-sm text-slate-300">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2 font-semibold text-sky-200">
                  <Activity className="h-4 w-4" /> Active Pods
                </span>
                <span className="text-2xl font-semibold text-white">{data.queueStatus.running}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2 font-semibold text-emerald-200">
                  <Cpu className="h-4 w-4" /> Available Pods
                </span>
                <span className="text-2xl font-semibold text-white">{availablePods}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2 font-semibold text-amber-200">
                  <Clock className="h-4 w-4" /> Queue Depth
                </span>
                <span className="text-2xl font-semibold text-white">{queued}</span>
              </div>
              <p className="mt-2 text-xs text-slate-400">
                {data.queueStatus.running} of {data.queueStatus.totalSlots} pods are busy. {availablePods > 0 ? `${availablePods} pod${availablePods === 1 ? " is" : "s are"} ready for the next run.` : "All pods are occupied right now."}
              </p>
              {experimentsInPipeline > 0 && (
                <p className="text-xs text-slate-500">
                  At this pace, queued experiments will clear in roughly {estimatedHours} hour{estimatedHours === 1 ? "" : "s"}.
                </p>
              )}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              icon={<Rocket className="h-5 w-5" />}
              title="Active experiments"
              value={activeExperiments}
              detail={`${running} running · ${validating} validating`}
              tone="from-sky-500/40 via-sky-400/20 to-transparent"
            />
            <MetricCard
              icon={<FlaskConical className="h-5 w-5" />}
              title="Completed lifetime"
              value={completed}
              detail="Auto & human validated"
              tone="from-emerald-500/40 via-emerald-400/20 to-transparent"
            />
            <MetricCard
              icon={<TrendingUp className="h-5 w-5" />}
              title="Queued next"
              value={queued}
              detail={`${data.queueStatus.queued} ready for scheduling`}
              tone="from-amber-500/40 via-amber-400/20 to-transparent"
            />
            <MetricCard
              icon={<AlertTriangle className="h-5 w-5" />}
              title="Needs attention"
              value={failed + canceled}
              detail={`${failed} failed · ${canceled} canceled`}
              tone="from-rose-500/40 via-rose-400/20 to-transparent"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
            <Link
              href="/validations/queue"
              className="inline-flex items-center gap-2 rounded-full border border-purple-500/60 bg-purple-500/10 px-4 py-2 font-semibold text-purple-100 transition hover:border-purple-400/80 hover:text-white"
            >
              <FlaskConical className="h-4 w-4" /> Validation queue
            </Link>
            <Link
              href="#runs-board"
              className="inline-flex items-center gap-2 rounded-full border border-sky-500/60 bg-sky-500/10 px-4 py-2 font-semibold text-sky-100 transition hover:border-sky-400/80 hover:text-white"
            >
              <Activity className="h-4 w-4" /> Experiments board
            </Link>
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-sky-500 via-blue-500 to-cyan-400 px-4 py-2 font-semibold text-slate-950 shadow-[0_18px_40px_-22px_rgba(56,189,248,0.65)] transition hover:from-sky-400 hover:via-blue-400 hover:to-cyan-300"
            >
              <Sparkles className="h-4 w-4" /> Create hypothesis
            </Link>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Pipeline health</h2>
            <p className="text-sm text-slate-400">Status distribution across every experiment.</p>
          </div>
          <span className="text-xs text-slate-500">Auto-refreshing every 5 seconds</span>
        </header>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">{statusTiles(data.counts)}</div>
      </section>

      <section id="runs-board" className="space-y-5">
        <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Experiments board</h2>
            <p className="text-sm text-slate-400">
              Drill into every run with live filters. Updated in real time.
            </p>
          </div>
          <span className="text-xs text-slate-500">
            Showing {(runsData?.items.length ?? 0)} of {runsData?.total ?? "—"} runs
          </span>
        </header>

        <div className="flex flex-col gap-4 rounded-3xl border border-slate-800/70 bg-slate-950/60 p-5">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-[1fr,1fr,auto] lg:items-end">
            <label className="flex flex-col gap-2 text-sm text-slate-300">
              Status
              <select
                className="rounded-2xl border border-slate-800 bg-slate-950 px-4 py-2 text-sm text-slate-100"
                value={statusFilter}
                onChange={(event) =>
                  setQueryParams({ status: event.target.value || undefined, page: "1" })
                }
              >
                <option value="">All statuses</option>
                {RUN_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-sm text-slate-300">
              Hypothesis
              <select
                className="rounded-2xl border border-slate-800 bg-slate-950 px-4 py-2 text-sm text-slate-100"
                value={hypothesisFilter}
                onChange={(event) =>
                  setQueryParams({ hypothesisId: event.target.value || undefined, page: "1" })
                }
              >
                <option value="">All hypotheses</option>
                {data.hypotheses.map((hypothesis) => (
                  <option key={hypothesis._id} value={hypothesis._id}>
                    {hypothesis.title}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center justify-end gap-2 text-xs text-slate-400">
              <span>Page {runsPage} of {totalPages}</span>
              <div className="flex items-center gap-2">
                <button
                  className="rounded-full border border-slate-700 px-3 py-1 font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
                  onClick={() => goToPage(runsPage - 1)}
                  disabled={runsPage <= 1}
                  type="button"
                >
                  Prev
                </button>
                <button
                  className="rounded-full border border-slate-700 px-3 py-1 font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
                  onClick={() => goToPage(runsPage + 1)}
                  disabled={runsPage >= totalPages}
                  type="button"
                >
                  Next
                </button>
              </div>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-800">
            {runsLoading && !runsData ? (
              <div className="p-8 text-center text-sm text-slate-500">Loading runs…</div>
            ) : runRows.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No runs match the current filters.
              </div>
            ) : (
              <table className="min-w-full divide-y divide-slate-800">
                <thead className="bg-slate-900/60">
                  <tr>
                    <HeaderCell>ID</HeaderCell>
                    <HeaderCell>Hypothesis</HeaderCell>
                    <HeaderCell>Status</HeaderCell>
                    <HeaderCell>Current Stage</HeaderCell>
                    <HeaderCell>Age</HeaderCell>
                    <HeaderCell>
                      <span className="sr-only">Inspect</span>
                    </HeaderCell>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                  {runRows.map(({ run, hypothesisTitle }) => {
                    const stageName = run.currentStage?.name?.replace("Stage_", "Stage ")
                    const stageProgress = Math.round((run.currentStage?.progress ?? 0) * 100)

                    const runHref = `/runs/${run._id}`
                    return (
                      <tr
                        key={run._id}
                        className="group cursor-pointer hover:bg-slate-900/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60"
                        role="button"
                        tabIndex={0}
                        onClick={() => router.push(runHref)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault()
                            router.push(runHref)
                          }
                        }}
                      >
                        <Cell>
                          <code className="text-xs">{run._id}</code>
                        </Cell>
                        <Cell>{hypothesisTitle ?? "—"}</Cell>
                        <Cell>
                          <StatusBadge status={run.status} />
                        </Cell>
                        <Cell>
                          {stageName ? (
                            <span className="text-xs text-slate-300">
                              <span className="font-medium text-slate-100">{stageName}</span>
                              <span className="ml-2 text-slate-400">{stageProgress}%</span>
                            </span>
                          ) : (
                            <span className="text-xs text-slate-500">—</span>
                          )}
                        </Cell>
                        <Cell>
                          {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
                        </Cell>
                        <Cell>
                          <Link
                            href={runHref}
                            onClick={(event) => event.stopPropagation()}
                            className="text-sm font-medium text-sky-400 hover:text-sky-300"
                          >
                            View
                          </Link>
                        </Cell>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <header className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-100">Live activity</h2>
          <Link
            href="#runs-board"
            className="inline-flex items-center gap-1 text-sm font-medium text-sky-400 hover:text-sky-300"
          >
            Full board
            <ArrowUpRight className="h-4 w-4" />
          </Link>
        </header>
        {latestRuns.length === 0 ? (
          <p className="text-sm text-slate-500">No recent runs have started yet.</p>
        ) : (
          <ul className="space-y-3">
            {latestRuns.map(({ run, hypothesis }) => {
              const createdLabel = formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })
              const stageName = run.currentStage?.name?.replace("Stage_", "Stage ")
              const stageProgress = Math.round((run.currentStage?.progress ?? 0) * 100)

              return (
                <li
                  key={run._id}
                  className="group relative cursor-pointer overflow-hidden rounded-3xl border border-slate-800/60 bg-slate-950/50 p-5 transition hover:-translate-y-0.5 hover:border-sky-500/60 focus-within:border-sky-500/60 focus-within:ring-2 focus-within:ring-sky-400/40"
                  role="button"
                  tabIndex={0}
                  onClick={() => router.push(`/runs/${run._id}`)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      router.push(`/runs/${run._id}`)
                    }
                  }}
                >
                  <div className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-sky-500/70 via-blue-500/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-1 items-start gap-4">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-800/70 bg-slate-900/80 text-sky-200">
                        <Activity className="h-5 w-5" />
                      </div>
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-3">
                          <StatusBadge status={run.status} />
                          <span className="text-xs text-slate-500">{createdLabel}</span>
                        </div>
                        <p className="text-sm font-semibold text-slate-100">
                          {hypothesis?.title ?? "Untitled hypothesis"}
                        </p>
                        {stageName ? (
                          <p className="text-xs text-slate-400">
                            {stageName} · {stageProgress}% complete
                          </p>
                        ) : (
                          <p className="text-xs text-slate-500">Stage data not yet available</p>
                        )}
                        <p className="text-[11px] text-slate-500">
                          Run ID <code className="text-slate-300">{run._id}</code>
                        </p>
                      </div>
                    </div>
                    <Link
                      href={`/runs/${run._id}`}
                      onClick={(event) => event.stopPropagation()}
                      className="inline-flex items-center gap-2 self-end rounded-full border border-slate-700/70 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-sky-500/70 hover:text-sky-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60"
                    >
                      Inspect run
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-slate-100">Momentum hypotheses</h2>
        {data.topHypotheses.length === 0 ? (
          <p className="text-sm text-slate-500">No recent runs linked to hypotheses.</p>
        ) : (
          <ul className="grid gap-4 md:grid-cols-2">
            {data.topHypotheses.map(({ hypothesis, runCount, lastRunAt }) => (
              <HypothesisCard
                key={hypothesis._id}
                hypothesis={hypothesis}
                runCount={runCount}
                lastRunAt={lastRunAt}
              />
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-slate-100">FAQ</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="text-sm font-semibold text-slate-100">How long does each run take?</h3>
            <p className="mt-2 text-sm text-slate-400">
              Most experiments take 5-6 hours. The hero panel shows the projected drain time for the current queue.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="text-sm font-semibold text-slate-100">What if I create many hypotheses?</h3>
            <p className="mt-2 text-sm text-slate-400">
              All hypotheses share the same pods. When capacity is saturated, new runs wait automatically until compute frees up.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="text-sm font-semibold text-slate-100">Where do I inspect a run?</h3>
            <p className="mt-2 text-sm text-slate-400">
              Jump into the run detail page for full telemetry, logs, and artifacts.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="text-sm font-semibold text-slate-100">What are the outputs?</h3>
            <p className="mt-2 text-sm text-slate-400">
              Completed runs deliver a research paper, plots, structured datasets, and reproducible code artifacts.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}

const statusTilesDefinitions = [
  { label: "Queued", status: "QUEUED" as RunStatus, tone: "from-slate-500/40 via-slate-500/20 to-transparent", descriptor: "Awaiting pod time" },
  { label: "Running", status: "RUNNING" as RunStatus, tone: "from-blue-500/40 via-blue-500/20 to-transparent", descriptor: "Actively experimenting" },
  { label: "Auto validating", status: "AUTO_VALIDATING" as RunStatus, tone: "from-purple-500/40 via-purple-500/20 to-transparent", descriptor: "Quality checks in progress" },
  { label: "Awaiting human", status: "AWAITING_HUMAN" as RunStatus, tone: "from-amber-500/40 via-amber-500/20 to-transparent", descriptor: "Needs human validation" },
  { label: "Failed", status: "FAILED" as RunStatus, tone: "from-rose-500/40 via-rose-500/20 to-transparent", descriptor: "Investigate these runs" }
]

function statusTiles(counts: Record<RunStatus, number>) {
  return statusTilesDefinitions.map(({ label, status, tone, descriptor }) => (
    <div
      key={status}
      className="relative overflow-hidden rounded-2xl border border-slate-800/70 bg-slate-950/60 p-5 shadow-[0_20px_60px_-40px_rgba(56,189,248,0.75)]"
    >
      <div className={cn("pointer-events-none absolute inset-0 bg-gradient-to-br opacity-50", tone)} />
      <div className="relative">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</div>
        <div className="mt-3 flex items-baseline gap-3">
          <span className="text-3xl font-semibold text-white">{counts[status] ?? 0}</span>
          <span className="text-xs text-slate-500">runs</span>
        </div>
        <div className="mt-4 h-1.5 w-full rounded-full bg-slate-800">
          <div
            className={cn("h-1.5 rounded-full bg-gradient-to-r", tone)}
            style={{ width: `${Math.min(100, (counts[status] ?? 0) * 12 + 4)}%` }}
          />
        </div>
        <p className="mt-3 text-xs text-slate-500">{descriptor}</p>
      </div>
    </div>
  ))
}

function MetricCard({
  icon,
  title,
  value,
  detail,
  tone
}: {
  icon: ReactNode
  title: string
  value: number
  detail: string
  tone: string
}) {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-slate-800/70 bg-slate-950/70 p-6">
      <div className={cn("pointer-events-none absolute inset-0 bg-gradient-to-br opacity-60", tone)} />
      <div className="relative flex flex-col gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-700/60 bg-slate-900/70 text-sky-100">
          {icon}
        </span>
        <div>
          <p className="text-sm font-semibold text-slate-200">{title}</p>
          <p className="text-3xl font-semibold text-white">{value}</p>
          <p className="text-xs text-slate-400">{detail}</p>
        </div>
      </div>
    </div>
  )
}

function HeaderCell({ children }: { children: ReactNode }) {
  return (
    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-400">
      {children}
    </th>
  )
}

function Cell({ children }: { children: ReactNode }) {
  return <td className="px-4 py-3 text-sm text-slate-200">{children}</td>
}

function HypothesisCard({
  hypothesis,
  runCount,
  lastRunAt
}: {
  hypothesis: Hypothesis
  runCount: number
  lastRunAt: Date | string
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  const ideaPreview =
    hypothesis.idea.length > 150 ? hypothesis.idea.substring(0, 150) + "..." : hypothesis.idea

  return (
    <li className="group relative overflow-hidden rounded-3xl border border-slate-800/60 bg-slate-950/50 p-6 transition hover:-translate-y-0.5 hover:border-purple-500/50">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-purple-500/10 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      <div className="relative flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-base font-semibold text-slate-100">{hypothesis.title}</h3>
          <span className="inline-flex items-center gap-2 rounded-full border border-purple-500/50 bg-purple-500/10 px-3 py-1 text-xs font-semibold text-purple-100">
            <TrendingUp className="h-3.5 w-3.5" /> {runCount} run{runCount === 1 ? "" : "s"}
          </span>
        </div>
        <p className="text-sm text-slate-300">
          {isExpanded ? hypothesis.idea : ideaPreview}
          {hypothesis.idea.length > 150 && (
            <button
              onClick={() => setIsExpanded((prev) => !prev)}
              className="ml-2 text-xs font-semibold text-sky-300 hover:text-sky-200"
            >
              {isExpanded ? "Show less" : "Read more"}
            </button>
          )}
        </p>
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>
            Last run {formatDistanceToNow(new Date(lastRunAt), { addSuffix: true })}
          </span>
          <Link
            href={`/overview?hypothesisId=${hypothesis._id}#runs-board`}
            className="inline-flex items-center gap-1 text-xs font-semibold text-sky-300 hover:text-sky-200"
          >
            Focus runs
            <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
      </div>
    </li>
  )
}
