"use client"

import { useState, useEffect } from "react"
import { type Run } from "@/lib/schemas/run"
import { STAGE_DESCRIPTIONS } from "@/lib/state/constants"

interface StageProgressPanelProps {
  run: Run
}

function formatDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`
  }
  return `${minutes}m ${seconds}s`
}

export function StageProgressPanel({ run }: StageProgressPanelProps) {
  const currentStage = run.currentStage
  const [now, setNow] = useState(Date.now())
  
  useEffect(() => {
    const interval = setInterval(() => {
      setNow(Date.now())
    }, 1000)
    return () => clearInterval(interval)
  }, [])
  
  if (!currentStage?.name) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
        <h3 className="text-sm font-semibold text-slate-200">Current Progress</h3>
        <p className="mt-2 text-sm text-slate-400">No active stage</p>
      </div>
    )
  }

  const progress = currentStage.progress || 0
  const iteration = currentStage.iteration || 0
  const maxIterations = currentStage.maxIterations || 1
  const goodNodes = currentStage.goodNodes || 0
  const buggyNodes = currentStage.buggyNodes || 0
  const totalNodes = currentStage.totalNodes || 0
  
  const stageTiming = run.stageTiming?.[currentStage.name]
  const stageStartedAt = stageTiming?.startedAt ? new Date(stageTiming.startedAt).getTime() : (run.startedAt ? new Date(run.startedAt).getTime() : now)
  const elapsedS = stageTiming?.elapsed_s || Math.floor((now - stageStartedAt) / 1000)
  
  const eta_s = elapsedS > 0 && progress > 0.01 
    ? Math.floor((elapsedS / progress) - elapsedS) 
    : null

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">
          {currentStage.name}: {STAGE_DESCRIPTIONS[currentStage.name]}
        </h3>
        <span className="text-xs font-medium text-sky-400">
          {Math.round(progress * 100)}%
        </span>
      </div>
      
      <div className="mt-4 h-2 w-full rounded-full bg-slate-800">
        <div 
          className="h-full rounded-full bg-sky-500 transition-all duration-500"
          style={{ width: `${progress * 100}%` }}
        />
      </div>
      
      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-slate-400">Iteration:</span>
          <span className="ml-2 font-mono text-slate-200">
            {iteration}/{maxIterations}
          </span>
        </div>
        
        <div>
          <span className="text-slate-400">Nodes:</span>
          <span className="ml-2 font-mono text-green-400">{goodNodes} good</span>
          <span className="ml-1 font-mono text-slate-500">/</span>
          <span className="ml-1 font-mono text-red-400">{buggyNodes} buggy</span>
          <span className="ml-1 font-mono text-slate-500">/</span>
          <span className="ml-1 font-mono text-slate-400">{totalNodes} total</span>
        </div>
        
        <div>
          <span className="text-slate-400">Elapsed:</span>
          <span className="ml-2 font-mono text-slate-200">
            {formatDuration(elapsedS)}
          </span>
        </div>
        
        {eta_s !== null && (
          <div>
            <span className="text-slate-400">ETA:</span>
            <span className="ml-2 font-mono text-amber-400">
              ~{formatDuration(eta_s)}
            </span>
          </div>
        )}
      </div>
      
      {currentStage.bestMetric && (
        <div className="mt-4 rounded border border-slate-700 bg-slate-950 p-3">
          <p className="text-xs font-medium text-slate-400">Best Metric</p>
          <p className="mt-1 font-mono text-xs text-slate-300">
            {currentStage.bestMetric}
          </p>
        </div>
      )}
    </div>
  )
}

