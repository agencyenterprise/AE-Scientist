"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { formatDistanceToNow } from "date-fns"
import Link from "next/link"
import { StartRunButton } from "./StartRunButton"

type IdeationStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED"

type IdeationIdea = {
  Name: string
  Title: string
  "Short Hypothesis": string
  Abstract: string
  Experiments: string[]
  "Risk Factors and Limitations": string[]
  "Related Work"?: string
}

type IdeationItem = {
  _id: string
  hypothesisId: string
  reflections: number
  status: IdeationStatus
  createdAt: string
  updatedAt: string
  startedAt?: string
  completedAt?: string
  failedAt?: string
  error?: string
  ideas?: IdeationIdea[]
  hypothesis?: {
    _id: string
    title: string
  } | null
}

type IdeationResponse = {
  items: IdeationItem[]
  total: number
  page: number
  pageSize: number
  counts: Record<IdeationStatus, number>
}

const STATUS_LABELS: Record<IdeationStatus, string> = {
  QUEUED: "Queued",
  RUNNING: "Running",
  COMPLETED: "Completed",
  FAILED: "Failed"
}

const STATUS_STYLE: Record<IdeationStatus, string> = {
  QUEUED: "bg-sky-500/10 text-sky-200 border-sky-500/40",
  RUNNING: "bg-violet-500/10 text-violet-200 border-violet-500/40",
  COMPLETED: "bg-emerald-500/10 text-emerald-200 border-emerald-500/40",
  FAILED: "bg-rose-500/10 text-rose-200 border-rose-500/40"
}

interface IdeationPageClientProps {
  initialData: IdeationResponse
  initialHypothesisId?: string
}

export function IdeationPageClient({
  initialData,
  initialHypothesisId
}: IdeationPageClientProps) {
  const [statusFilter, setStatusFilter] = useState<IdeationStatus | "ALL">("ALL")
  const [hypothesisFilter, setHypothesisFilter] = useState(initialHypothesisId ?? "")
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const pageSize = initialData.pageSize ?? 25
  const detailRef = useRef<HTMLDivElement | null>(null)

  const { data, isFetching } = useQuery({
    queryKey: ["ideation-queue", statusFilter, hypothesisFilter, page],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set("page", page.toString())
      params.set("pageSize", pageSize.toString())
      if (statusFilter !== "ALL") {
        params.set("status", statusFilter)
      }
      if (hypothesisFilter) {
        params.set("hypothesisId", hypothesisFilter)
      }
      const res = await fetch(`/api/ideations?${params.toString()}`)
      if (!res.ok) {
        throw new Error("Failed to load ideation queue")
      }
      return (await res.json()) as IdeationResponse
    },
    initialData,
    keepPreviousData: true,
    refetchInterval: 10000,
    refetchOnWindowFocus: false
  })

  const totalPages = useMemo(() => {
    if (!data) return 1
    return Math.max(1, Math.ceil(data.total / pageSize))
  }, [data, pageSize])

  const items = data?.items ?? []
  const counts = data?.counts ?? initialData.counts

  useEffect(() => {
    if (items.length === 0) {
      setSelectedId(null)
      return
    }

    if (hypothesisFilter) {
      const match = items.find((item) => item.hypothesisId === hypothesisFilter)
      if (match) {
        setSelectedId(match._id)
        return
      }
    }

    setSelectedId((prev) => {
      if (prev && items.some((item) => item._id === prev)) {
        return prev
      }
      return items[0]?._id ?? null
    })
  }, [items, hypothesisFilter])

  const selectedItem = useMemo(
    () => items.find((item) => item._id === selectedId) ?? null,
    [items, selectedId]
  )

  useEffect(() => {
    if (selectedItem) {
      detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    }
  }, [selectedItem])

  const activeHypothesisTitle = useMemo(() => {
    if (!hypothesisFilter) return null
    const pools = [items, initialData.items]
    for (const pool of pools) {
      const match = pool.find((item) => item.hypothesisId === hypothesisFilter)
      if (match?.hypothesis?.title) {
        return match.hypothesis.title
      }
    }
    return null
  }, [hypothesisFilter, items, initialData.items])

  const setStatus = (next: IdeationStatus | "ALL") => {
    setStatusFilter(next)
    setPage(1)
  }

  const setHypothesis = (next: string) => {
    setHypothesisFilter(next)
    setPage(1)
  }

  const goToPage = (next: number) => {
    setPage(Math.max(1, Math.min(next, totalPages)))
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-10">
      <header className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-white sm:text-4xl">Ideation Dashboard</h1>
            <p className="mt-2 max-w-xl text-sm text-slate-300">
              Live progress for active ideation requests.
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-full border border-slate-700 bg-slate-900/60 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-sky-500/60 hover:text-white"
          >
            Back to hypotheses
          </Link>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(["QUEUED", "RUNNING", "COMPLETED", "FAILED"] as IdeationStatus[]).map((status) => (
            <div
              key={status}
              className="rounded-xl border border-slate-800/70 bg-slate-950/60 p-4 shadow-[0_20px_60px_-50px_rgba(56,189,248,0.3)]"
            >
              <p className="text-sm font-medium text-slate-300">
                {STATUS_LABELS[status]}
              </p>
              <p className="mt-2 text-3xl font-semibold text-white">
                {counts?.[status] ?? 0}
              </p>
            </div>
          ))}
        </div>
      </header>

      <div className="rounded-[2rem] border border-slate-800/80 bg-slate-950/70 p-6 shadow-[0_40px_120px_-70px_rgba(14,165,233,0.65)]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-lg font-semibold text-white">Requests</h2>
          <div className="flex flex-wrap items-center gap-2">
            <FilterChip
              active={statusFilter === "ALL"}
              onClick={() => setStatus("ALL")}
              label={`All (${data?.total ?? initialData.total})`}
            />
            {(["QUEUED", "RUNNING", "COMPLETED", "FAILED"] as IdeationStatus[]).map((status) => (
              <FilterChip
                key={status}
                active={statusFilter === status}
                onClick={() => setStatus(status)}
                label={`${STATUS_LABELS[status]} (${counts?.[status] ?? 0})`}
              />
            ))}
          </div>
        </div>

        {hypothesisFilter && (
          <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-slate-800/80 bg-slate-900/40 px-4 py-3 text-sm text-slate-300">
            <span className="font-semibold text-slate-400">Filtered hypothesis</span>
            <span className="line-clamp-1 font-medium text-slate-200">
              {activeHypothesisTitle ?? hypothesisFilter}
            </span>
            <button
              onClick={() => setHypothesis("")}
              className="rounded-full border border-slate-700 px-3 py-1 text-xs font-medium text-slate-300 transition hover:border-rose-500/60 hover:text-rose-200"
            >
              Clear
            </button>
          </div>
        )}

        <div className="mt-6 overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-800 text-left text-sm text-slate-200">
            <thead className="bg-slate-900/60 text-xs font-medium text-slate-400">
              <tr>
                <th className="px-4 py-3 font-medium">Hypothesis</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Reflections</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium">Updated</th>
                <th className="px-4 py-3 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {items.length === 0 && !isFetching && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-slate-500">
                    Nothing in this slice yet. New ideation requests will appear here immediately.
                  </td>
                </tr>
              )}
              {items.map((item) => {
                const hypothesisTitle = item.hypothesis?.title ?? "Untitled hypothesis"
                const createdLabel = formatDistanceToNow(new Date(item.createdAt), {
                  addSuffix: true
                })
                const updatedLabel = formatDistanceToNow(
                  new Date(item.completedAt ?? item.updatedAt ?? item.createdAt),
                  { addSuffix: true }
                )
                const primaryIdea = item.ideas?.[0]

                return (
                  <tr
                    key={item._id}
                    onClick={() => setSelectedId(item._id)}
                    className={`cursor-pointer transition ${
                      item._id === selectedId ? "bg-slate-900/60" : "hover:bg-slate-900/40"
                    }`}
                    aria-selected={item._id === selectedId}
                  >
                    <td className="px-4 py-4 align-top">
                      <div className="space-y-2">
                        <span className="line-clamp-2 font-semibold text-white">
                          {hypothesisTitle}
                        </span>
                        {primaryIdea && (
                          <p className="line-clamp-3 text-xs text-slate-400">
                            {primaryIdea["Short Hypothesis"]}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${STATUS_STYLE[item.status]}`}
                      >
                        {STATUS_LABELS[item.status]}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-200">{item.reflections}</td>
                    <td className="px-4 py-4 text-xs text-slate-400">{createdLabel}</td>
                    <td className="px-4 py-4 text-xs text-slate-400">{updatedLabel}</td>
                    <td className="px-4 py-4 text-xs text-slate-400">
                      {item.status === "FAILED" && item.error
                        ? item.error
                        : item.status === "COMPLETED" && primaryIdea
                          ? `Primary idea: ${primaryIdea.Title}`
                          : "—"}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex h-6 items-center justify-center">
          <span
            className={`h-2 w-2 rounded-full bg-slate-500 transition-opacity ${
              isFetching ? "animate-pulse opacity-100" : "opacity-0"
            }`}
            aria-hidden="true"
          />
          <span className="sr-only" aria-live="polite">
            {isFetching ? "Refreshing data" : "Idle"}
          </span>
        </div>

        <div className="mt-6 flex items-center justify-between text-sm text-slate-400">
          <span>
            Page {data?.page ?? page} of {totalPages}
          </span>
          <div className="flex items-center gap-3">
            <button
              className="rounded-full border border-slate-700 px-3 py-1.5 text-sm font-medium text-slate-300 transition hover:border-sky-500/60 hover:text-white disabled:opacity-30"
              onClick={() => goToPage(page - 1)}
              disabled={page <= 1}
            >
              Prev
            </button>
            <button
              className="rounded-full border border-slate-700 px-3 py-1.5 text-sm font-medium text-slate-300 transition hover:border-sky-500/60 hover:text-white disabled:opacity-30"
              onClick={() => goToPage(page + 1)}
              disabled={page >= totalPages}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <div
        ref={detailRef}
        className="rounded-[2rem] border border-slate-800/80 bg-slate-950/70 p-6 shadow-[0_30px_90px_-60px_rgba(56,189,248,0.45)]"
      >
        {selectedItem ? (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium ${STATUS_STYLE[selectedItem.status]}`}
              >
                {STATUS_LABELS[selectedItem.status]}
              </span>
              <span className="rounded-full border border-slate-700 px-3 py-1 text-sm font-medium text-slate-200">
                {selectedItem.reflections} reflections
              </span>
            </div>

            <div>
              <h3 className="text-2xl font-semibold text-white">
                {selectedItem.hypothesis?.title ?? "Untitled hypothesis"}
              </h3>
              <p className="mt-2 text-sm text-slate-300">
                Created{" "}
                {formatDistanceToNow(new Date(selectedItem.createdAt), { addSuffix: true })}
                {selectedItem.completedAt
                  ? ` · Completed ${formatDistanceToNow(new Date(selectedItem.completedAt), {
                      addSuffix: true
                    })}`
                  : selectedItem.startedAt
                    ? ` · Started ${formatDistanceToNow(new Date(selectedItem.startedAt), {
                        addSuffix: true
                      })}`
                    : ""}
              </p>
            </div>

            {selectedItem.status === "FAILED" && selectedItem.error && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                {selectedItem.error}
              </div>
            )}

            <StartRunButton
              hypothesisId={selectedItem.hypothesisId}
              disabled={selectedItem.status !== "COMPLETED" || !selectedItem.ideas?.length}
              label={
                selectedItem.status === "COMPLETED" && selectedItem.ideas?.length
                  ? "Launch Experiment"
                  : "Awaiting ideas"
              }
            />

            <div className="grid gap-3 text-sm text-slate-300 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <p className="text-xs font-medium text-slate-400">Hypothesis ID</p>
                <p className="mt-1 break-all text-slate-200">{selectedItem.hypothesisId}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-400">Request ID</p>
                <p className="mt-1 break-all text-slate-200">{selectedItem._id}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-slate-400">Last updated</p>
                <p className="mt-1 text-slate-200">
                  {new Date(
                    selectedItem.completedAt ?? selectedItem.updatedAt ?? selectedItem.createdAt
                  ).toLocaleString()}
                </p>
              </div>
              {selectedItem.startedAt && (
                <div>
                  <p className="text-xs font-medium text-slate-400">Started</p>
                  <p className="mt-1 text-slate-200">
                    {new Date(selectedItem.startedAt).toLocaleString()}
                  </p>
                </div>
              )}
              {selectedItem.completedAt && (
                <div>
                  <p className="text-xs font-medium text-slate-400">Completed</p>
                  <p className="mt-1 text-slate-200">
                    {new Date(selectedItem.completedAt).toLocaleString()}
                  </p>
                </div>
              )}
              {selectedItem.failedAt && (
                <div>
                  <p className="text-xs font-medium text-slate-400">Failed</p>
                  <p className="mt-1 text-slate-200">
                    {new Date(selectedItem.failedAt).toLocaleString()}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-4">
              {(selectedItem.ideas ?? []).length === 0 && (
                <p className="text-sm text-slate-400">
                  No ideas generated yet. If ideation just finished, give the page a moment to update.
                </p>
              )}
              {(selectedItem.ideas ?? []).map((idea, index) => (
                <div
                  key={`${idea.Name}-${index}`}
                  className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-slate-400">Idea {index + 1}</p>
                      <h4 className="mt-1 text-lg font-semibold text-white">{idea.Title}</h4>
                    </div>
                    <span className="rounded-full bg-slate-800/60 px-3 py-1 text-xs font-medium text-slate-300">
                      {idea.Name}
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-slate-300">{idea["Short Hypothesis"]}</p>

                  <div className="mt-4 space-y-3 text-sm text-slate-300">
                    {idea.Abstract && (
                      <section>
                        <h5 className="text-xs font-medium text-slate-400">Abstract</h5>
                        <p className="mt-1 whitespace-pre-line leading-relaxed text-slate-300">
                          {idea.Abstract}
                        </p>
                      </section>
                    )}
                    {idea.Experiments.length > 0 && (
                      <section>
                        <h5 className="text-xs font-medium text-slate-400">Experiments</h5>
                        <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-300">
                          {idea.Experiments.map((experiment, idx) => (
                            <li key={idx}>{experiment}</li>
                          ))}
                        </ul>
                      </section>
                    )}
                    {idea["Risk Factors and Limitations"].length > 0 && (
                      <section>
                        <h5 className="text-xs font-medium text-slate-400">Risks &amp; limitations</h5>
                        <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-300">
                          {idea["Risk Factors and Limitations"].map((risk, idx) => (
                            <li key={idx}>{risk}</li>
                          ))}
                        </ul>
                      </section>
                    )}
                    {idea["Related Work"] && (
                      <section>
                        <h5 className="text-xs font-medium text-slate-400">Related work</h5>
                        <p className="mt-1 whitespace-pre-line text-slate-300">
                          {idea["Related Work"]}
                        </p>
                      </section>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-400">
            Select an ideation request from the table above to view the generated ideas and launch
            experiments.
          </p>
        )}
      </div>
    </div>
  )
}

function FilterChip({
  active,
  onClick,
  label
}: {
  active: boolean
  onClick: () => void
  label: string
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-sm font-medium transition ${
        active
          ? "border-sky-500/60 bg-sky-500/10 text-sky-100 shadow-[0_8px_24px_-18px_rgba(14,165,233,0.7)]"
          : "border-slate-800/70 bg-slate-900/60 text-slate-300 hover:border-sky-500/40 hover:text-sky-100"
      }`}
    >
      {label}
    </button>
  )
}
