"use client"

import { useState, useTransition } from "react"
import type { Artifact } from "@/lib/schemas/artifact"

export function FinalPdfBanner({ runId, artifacts }: { runId: string; artifacts: Artifact[] }) {
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [downloadingKey, setDownloadingKey] = useState<string | null>(null)

  // Find the final PDF artifact - look for "final" in filename and .pdf extension
  const finalPdf = artifacts.find(
    (artifact) => 
      artifact.key.toLowerCase().includes("final") && 
      artifact.key.toLowerCase().endsWith(".pdf")
  )

  // Find the tar.gz artifact
  const tarGz = artifacts.find(
    (artifact) => artifact.key.toLowerCase().endsWith(".tar.gz")
  )

  // Don't show banner if neither artifact is available
  if (!finalPdf && !tarGz) {
    return null
  }

  const handleDownload = (artifact: Artifact) => {
    startTransition(async () => {
      setError(null)
      setDownloadingKey(artifact.key)
      try {
        const response = await fetch(`/api/runs/${runId}/artifacts/presign`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ action: "get", key: artifact.key })
        })
        if (!response.ok) {
          throw new Error(`Failed to presign: ${response.status}`)
        }
        const { url } = (await response.json()) as { url: string }
        window.open(url, "_blank")
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setDownloadingKey(null)
      }
    })
  }

  return (
    <div className="rounded-lg border border-emerald-800 bg-gradient-to-r from-emerald-950/50 to-emerald-900/30 p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/20">
          <svg
            className="h-6 w-6 text-emerald-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        </div>
        <div>
          <h3 className="text-base font-semibold text-emerald-100">Final Results Ready</h3>
          <p className="text-sm text-emerald-300/80">
            Download the final paper and experiment artifacts
          </p>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {finalPdf && (
          <div className="flex items-center justify-between rounded-lg border border-emerald-700/50 bg-emerald-950/30 p-4">
            <div className="flex items-center gap-3">
              <svg
                className="h-5 w-5 text-emerald-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                />
              </svg>
              <div>
                <div className="text-sm font-semibold text-emerald-100">Final Paper (PDF)</div>
                <div className="text-xs text-emerald-400/70">
                  {finalPdf.size ? formatBytes(finalPdf.size) : "Unknown size"}
                </div>
              </div>
            </div>
            <button
              className="rounded border border-emerald-600 bg-emerald-500/20 px-4 py-2 text-sm font-medium text-emerald-100 transition-colors hover:bg-emerald-500/30 disabled:opacity-40"
              onClick={() => handleDownload(finalPdf)}
              disabled={pending}
            >
              {downloadingKey === finalPdf.key ? "..." : "Download"}
            </button>
          </div>
        )}

        {tarGz && (
          <div className="flex items-center justify-between rounded-lg border border-emerald-700/50 bg-emerald-950/30 p-4">
            <div className="flex items-center gap-3 flex-1">
              <svg
                className="h-5 w-5 text-emerald-400 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z"
                />
              </svg>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-emerald-100">Experiment Archive</div>
                <div className="text-xs text-emerald-400/70">
                  {tarGz.size ? formatBytes(tarGz.size) : "Unknown size"} · Complete experiment data
                </div>
                <div className="text-xs text-emerald-400/50 mt-0.5">
                  Includes code, logs, plots, and all intermediate artifacts
                </div>
              </div>
            </div>
            <button
              className="rounded border border-emerald-600 bg-emerald-500/20 px-4 py-2 text-sm font-medium text-emerald-100 transition-colors hover:bg-emerald-500/30 disabled:opacity-40 flex-shrink-0 ml-3"
              onClick={() => handleDownload(tarGz)}
              disabled={pending}
            >
              {downloadingKey === tarGz.key ? "..." : "Download"}
            </button>
          </div>
        )}
      </div>

      {error && <p className="mt-3 text-sm text-rose-400">{error}</p>}
    </div>
  )
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "—"
  const units = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`
}

