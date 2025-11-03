interface QueueStatusProps {
  totalSlots: number
  running: number
  queued: number
}

export function QueueStatus({ totalSlots, running, queued }: QueueStatusProps) {
  const available = Math.max(0, totalSlots - running)
  const utilizationPercent = Math.round((running / totalSlots) * 100)

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">RunPod Queue Status</h2>
        <span className="text-xs text-slate-400">
          {utilizationPercent}% utilization
        </span>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border border-slate-700 bg-slate-950/60 p-4">
          <div className="text-xs uppercase text-slate-400">Max Pods</div>
          <div className="mt-2 text-2xl font-semibold text-slate-100">{totalSlots}</div>
        </div>

        <div className="rounded-lg border border-blue-700 bg-blue-950/60 p-4">
          <div className="text-xs uppercase text-blue-400">Running</div>
          <div className="mt-2 text-2xl font-semibold text-blue-100">{running}</div>
        </div>

        <div className="rounded-lg border border-emerald-700 bg-emerald-950/60 p-4">
          <div className="text-xs uppercase text-emerald-400">Available</div>
          <div className="mt-2 text-2xl font-semibold text-emerald-100">{available}</div>
        </div>

        <div className="rounded-lg border border-amber-700 bg-amber-950/60 p-4">
          <div className="text-xs uppercase text-amber-400">Queued</div>
          <div className="mt-2 text-2xl font-semibold text-amber-100">{queued}</div>
        </div>
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Pod Usage</span>
          <span>
            {running} / {totalSlots} pods active
          </span>
        </div>
        <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className="h-3 bg-gradient-to-r from-blue-500 to-sky-500 transition-all"
            style={{ width: `${utilizationPercent}%` }}
          />
        </div>
      </div>

      {queued > 0 && (
        <div className="mt-4 rounded border border-amber-700/40 bg-amber-950/20 p-3">
          <p className="text-sm text-amber-200">
            <span className="font-semibold">{queued}</span> run{queued !== 1 ? "s" : ""} waiting
            for available pod slots
          </p>
        </div>
      )}
    </div>
  )
}

