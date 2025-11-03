"use client"

import { type Run } from "@/lib/schemas/run"
import { STAGE_DESCRIPTIONS } from "@/lib/state/constants"

interface StageTimingViewProps {
  run: Run
}

export function StageTimingView({ run }: StageTimingViewProps) {
  const stages = ["Stage_1", "Stage_2", "Stage_3", "Stage_4"] as const
  const timing = run.stageTiming || {}
  
  const totalDuration = stages.reduce((sum, stage) => {
    return sum + (timing[stage]?.duration_s || timing[stage]?.elapsed_s || 0)
  }, 0)
  
  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    if (mins < 60) return `${mins}m ${secs}s`
    const hours = Math.floor(mins / 60)
    const remainMins = mins % 60
    return `${hours}h ${remainMins}m`
  }

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
      <h3 className="text-sm font-semibold text-slate-200">Stage Timing</h3>
      
      {totalDuration > 0 && (
        <div className="mt-2 text-xs text-slate-400">
          Total elapsed: <span className="font-mono text-slate-300">{formatTime(totalDuration)}</span>
        </div>
      )}
      
      <div className="mt-4 space-y-3">
        {stages.map((stage) => {
          const stageData = timing[stage]
          const duration = stageData?.duration_s || stageData?.elapsed_s || 0
          const isComplete = !!stageData?.duration_s
          const isActive = run.currentStage?.name === stage && !isComplete
          
          if (!stageData && !isActive) return null
          
          return (
            <div key={stage} className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-slate-300">{stage}</span>
                  <span className="text-xs text-slate-500">{STAGE_DESCRIPTIONS[stage]}</span>
                  {isActive && (
                    <span className="inline-flex items-center rounded-full bg-sky-500/10 px-2 py-0.5 text-xs text-sky-400">
                      Running
                    </span>
                  )}
                  {isComplete && (
                    <span className="inline-flex items-center rounded-full bg-green-500/10 px-2 py-0.5 text-xs text-green-400">
                      ✓
                    </span>
                  )}
                </div>
              </div>
              <div className="font-mono text-xs text-slate-300">
                {formatTime(duration)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

