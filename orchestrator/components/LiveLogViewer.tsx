"use client"

import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

interface LogEntry {
  _id: string
  timestamp: Date
  message?: string | null
  level?: string | null
  data: {
    message?: string
    level?: string
    source?: string
  }
}

interface LiveLogViewerProps {
  runId: string
}

export function LiveLogViewer({ runId }: LiveLogViewerProps) {
  const [filter, setFilter] = useState<"all" | "info" | "warn" | "error">("all")
  
  const { data: logs } = useQuery<LogEntry[]>({
    queryKey: ["logs", runId, filter],
    queryFn: async () => {
      const params = new URLSearchParams({ type: "ai.run.log" })
      if (filter !== "all") {
        params.append("level", filter)
      }
      const res = await fetch(`/api/runs/${runId}/events?${params}`)
      if (!res.ok) throw new Error("Failed to fetch logs")
      const data = await res.json()
      return data.items || []
    },
    refetchInterval: 2000
  })

  const filteredLogs = logs?.filter(log => {
    if (filter === "all") return true
    const level = log.level || log.data?.level
    return level === filter
  }) || []

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">Live Logs</h3>
        
        <div className="flex gap-2">
          {(["all", "info", "warn", "error"] as const).map((level) => (
            <button
              key={level}
              onClick={() => setFilter(level)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                filter === level
                  ? "bg-sky-600/40 text-sky-100"
                  : "text-slate-400 hover:bg-slate-800"
              }`}
            >
              {level}
            </button>
          ))}
        </div>
      </div>
      
      <div className="mt-4 max-h-96 space-y-1 overflow-y-auto font-mono text-xs">
        {filteredLogs.length === 0 && (
          <p className="text-slate-500">No logs yet...</p>
        )}
        
        {filteredLogs.map((log) => {
          const level = log.level || log.data?.level || "info"
          const message = log.message || log.data?.message || ""
          const source = log.data?.source
          
          const levelColor = {
            info: "text-slate-300",
            warn: "text-amber-400",
            error: "text-red-400",
            debug: "text-slate-500"
          }[level] || "text-slate-300"
          
          const timestamp = new Date(log.timestamp).toLocaleTimeString()
          
          return (
            <div key={log._id} className="flex gap-2">
              <span className="text-slate-500">{timestamp}</span>
              {source && (
                <span className="rounded bg-sky-900/30 px-1.5 py-0.5 text-sky-400 font-semibold">
                  {source}
                </span>
              )}
              <span className={levelColor}>{message}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

