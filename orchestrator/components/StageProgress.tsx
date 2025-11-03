import { STAGE_DESCRIPTIONS, type StageName } from "@/lib/state/constants"

type StageProgressItem = {
  name: StageName
  progress?: number
  status?: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED"
  substage?: string
  substageFull?: string
}

export function StageProgress({ stages }: { stages: StageProgressItem[] }) {
  return (
    <div className="space-y-4">
      {stages.map((stage) => (
        <div key={stage.name} className="space-y-2">
          <div className="flex items-center justify-between text-sm text-slate-300">
            <div className="flex-1">
              <p className="font-medium text-slate-100">{readableStage(stage.name)}</p>
              <p className="text-xs text-slate-400">{STAGE_DESCRIPTIONS[stage.name]}</p>
              {stage.substage && stage.status === "RUNNING" && (
                <p className="mt-1 text-xs font-medium text-sky-400">
                  → {stage.substageFull || stage.substage}
                </p>
              )}
            </div>
            {stage.status && <span className="text-xs uppercase text-slate-400">{stage.status}</span>}
          </div>
          <div className="h-2 w-full rounded bg-slate-800">
            <div
              className="h-2 rounded bg-sky-500 transition-all"
              style={{ width: `${normalize(stage.progress)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function readableStage(stage: StageName) {
  return stage.replace("Stage_", "Stage ")
}

function normalize(progress?: number) {
  const value = Math.round((progress ?? 0) * 100)
  return Math.min(100, Math.max(0, value))
}
