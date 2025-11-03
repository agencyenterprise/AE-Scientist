"use client"

import { useQuery } from "@tanstack/react-query"
import type { Event } from "@/lib/schemas/event"

interface CurrentActivityBannerProps {
  runId: string
}

export function CurrentActivityBanner({ runId }: CurrentActivityBannerProps) {
  const { data, isLoading } = useQuery<{ items: Event[] }>({
    queryKey: ["latest-activity", runId],
    queryFn: async () => {
      const res = await fetch(`/api/runs/${runId}/events?type=ai.run.log&pageSize=1`)
      if (!res.ok) throw new Error("Failed to fetch latest activity")
      return res.json()
    },
    refetchInterval: 2000, // Poll every 2 seconds
    refetchOnWindowFocus: true
  })

  if (isLoading) {
    return (
      <div className="mb-4 rounded-lg border border-slate-700/50 bg-slate-900/30 p-4">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 animate-pulse rounded-full bg-slate-500" />
          <p className="text-sm text-slate-400">Loading activity...</p>
        </div>
      </div>
    )
  }

  const latest = data?.items?.[0]
  const message = latest?.message || (latest?.data as any)?.message
  if (!message) {
    return (
      <div className="mb-4 rounded-lg border border-slate-700/50 bg-slate-900/30 p-4">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-slate-600" />
          <p className="text-sm text-slate-400">Waiting for activity...</p>
        </div>
      </div>
    )
  }

  // Determine color based on message content
  const level = latest.level || (latest.data as any)?.level || "info"
  
  let colorClasses = {
    border: "border-sky-800/50",
    bg: "bg-sky-950/30",
    dot: "bg-sky-400",
    text: "text-sky-100",
    time: "text-sky-400"
  }

  if (level === "error" || message.includes("❌") || message.includes("Failed")) {
    colorClasses = {
      border: "border-red-800/50",
      bg: "bg-red-950/30",
      dot: "bg-red-400",
      text: "text-red-100",
      time: "text-red-400"
    }
  } else if (level === "warn" || message.includes("⚠️")) {
    colorClasses = {
      border: "border-amber-800/50",
      bg: "bg-amber-950/30",
      dot: "bg-amber-400",
      text: "text-amber-100",
      time: "text-amber-400"
    }
  } else if (message.includes("✓") || message.includes("✅") || message.includes("completed")) {
    colorClasses = {
      border: "border-green-800/50",
      bg: "bg-green-950/30",
      dot: "bg-green-400",
      text: "text-green-100",
      time: "text-green-400"
    }
  }

  const timestamp = new Date(latest.timestamp).toLocaleTimeString()

  return (
    <div className={`mb-4 rounded-lg border ${colorClasses.border} ${colorClasses.bg} p-4`}>
      <div className="flex items-center gap-3">
        <div className={`h-2 w-2 animate-pulse rounded-full ${colorClasses.dot}`} />
        <p className={`flex-1 text-sm font-medium ${colorClasses.text}`}>
          {message}
        </p>
        <span className={`text-xs ${colorClasses.time}`}>
          {timestamp}
        </span>
      </div>
    </div>
  )
}

