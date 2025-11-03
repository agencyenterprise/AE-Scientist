"use client"

import { useState, useTransition } from "react"
import type { Artifact } from "@/lib/schemas/artifact"

export function ArtifactList({ runId, artifacts }: { runId: string; artifacts: Artifact[] }) {
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState<string | null>(null)

  const handleDownload = (key: string) => {
    startTransition(async () => {
      setError(null)
      try {
        const response = await fetch(`/api/runs/${runId}/artifacts/presign`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ action: "get", key })
        })
        if (!response.ok) {
          throw new Error(`Failed to presign: ${response.status}`)
        }
        const { url } = (await response.json()) as { url: string }
        window.open(url, "_blank")
      } catch (err) {
        setError((err as Error).message)
      }
    })
  }

  // Filter out .png files since they're already shown in the plots section
  const nonImageArtifacts = artifacts.filter(artifact => !artifact.key.toLowerCase().endsWith('.png'))

  if (nonImageArtifacts.length === 0) {
    return <p className="text-sm text-slate-500">No artifacts yet.</p>
  }

  return (
    <div className="space-y-3">
      {error && <p className="text-sm text-rose-400">{error}</p>}
      <p className="text-xs text-slate-400 italic">
        Other PDFs are intermediate reflections. The final paper is highlighted above.
      </p>
      <ul className="space-y-2">
        {nonImageArtifacts.map((artifact) => (
          <li
            key={artifact._id}
            className="flex items-center justify-between rounded border border-slate-800 bg-slate-900/40 px-4 py-3 text-sm"
          >
            <div>
              <div className="font-medium text-slate-100">{artifact.key}</div>
              <div className="text-xs text-slate-400">
                {artifact.size ? formatBytes(artifact.size) : "Unknown size"} ·
                Uploaded {new Date(artifact.createdAt).toLocaleString()}
              </div>
            </div>
            <button
              className="rounded border border-slate-700 px-3 py-1 text-xs uppercase tracking-wide text-slate-100 disabled:opacity-40"
              onClick={() => handleDownload(artifact.key)}
              disabled={pending}
            >
              Download
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "—"
  const units = ["B", "KB", "MB", "GB", "TB"]
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** exponent
  return `${value.toFixed(1)} ${units[exponent]}`
}
