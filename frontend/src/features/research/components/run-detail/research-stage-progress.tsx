"use client";

import type { StageProgress } from "@/types/research";

interface ResearchStageProgressProps {
  progress: StageProgress;
}

/**
 * Stage progress section showing iteration details and progress bar
 */
export function ResearchStageProgress({ progress }: ResearchStageProgressProps) {
  const progressPercent = Math.round(progress.progress * 100);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
      <h2 className="mb-4 text-lg font-semibold text-white">Stage Progress</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="text-xs text-slate-400">Iteration</p>
          <p className="text-lg font-medium text-white">
            {progress.iteration} / {progress.max_iterations}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400">Best Metric</p>
          <p className="text-lg font-medium text-white">{progress.best_metric || "-"}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">Total Nodes</p>
          <p className="text-lg font-medium text-white">{progress.total_nodes}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">Good / Buggy</p>
          <p className="text-lg font-medium text-white">
            <span className="text-emerald-400">{progress.good_nodes}</span>
            {" / "}
            <span className="text-red-400">{progress.buggy_nodes}</span>
          </p>
        </div>
      </div>
      <div className="mt-4">
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className="h-full rounded-full bg-emerald-500 transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
    </div>
  );
}
