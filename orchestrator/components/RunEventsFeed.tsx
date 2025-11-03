"use client"

import { useQuery } from "@tanstack/react-query"
import type { Event } from "@/lib/schemas/event"

export function RunEventsFeed({ runId }: { runId: string }) {
  const { data, isLoading, error } = useQuery<{ items: Event[] }>(
    {
      queryKey: ["run-events", runId],
      queryFn: async () => {
        const response = await fetch(`/api/runs/${runId}/events?pageSize=100`, {
          cache: "no-store"
        })
        if (!response.ok) {
          throw new Error(`Failed to fetch events: ${response.status}`)
        }
        return (await response.json()) as { items: Event[] }
      },
      refetchInterval: 5000
    }
  )

  if (isLoading) {
    return <p className="text-sm text-slate-400">Loading events…</p>
  }

  if (error) {
    return <p className="text-sm text-rose-400">Failed to load events.</p>
  }

  const events = data?.items ?? []

  if (events.length === 0) {
    return <p className="text-sm text-slate-500">No events yet.</p>
  }

  return (
    <div className="space-y-3 text-sm">
      {events.map((event) => (
        <div key={event._id} className="rounded border border-slate-800 bg-slate-900/40 p-3">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>{event.type}</span>
            <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
          </div>
          {event.message && <p className="mt-2 text-slate-200">{event.message}</p>}
          {event.payload && (
            <pre className="mt-2 overflow-auto rounded bg-slate-950/80 p-2 text-xs text-slate-400">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          )}
        </div>
      ))}
    </div>
  )
}
