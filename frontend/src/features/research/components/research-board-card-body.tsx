"use client";

import { AlertCircle, Cpu } from "lucide-react";
import { ProgressBar } from "@/shared/components/ui/progress-bar";
import { getStageBadge } from "../utils/research-utils";

export interface ResearchBoardCardBodyProps {
  ideaTitle: string;
  ideaHypothesis: string | null;
  status: string;
  errorMessage: string | null;
  currentStage: string | null;
  progress: number | null;
  gpuType: string | null;
}

export function ResearchBoardCardBody({
  ideaTitle,
  ideaHypothesis,
  status,
  errorMessage,
  currentStage,
  progress,
  gpuType,
}: ResearchBoardCardBodyProps) {
  return (
    <div className="p-5">
      {/* Title */}
      <h3 className="text-lg font-semibold text-white">{ideaTitle}</h3>

      {/* Hypothesis */}
      {ideaHypothesis && (
        <p className="mt-2 text-sm leading-relaxed text-slate-400">{ideaHypothesis}</p>
      )}

      {/* Error Message for Failed Runs */}
      {status === "failed" && errorMessage && (
        <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" />
            <p className="text-sm text-red-300">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="mt-5 grid gap-4 sm:grid-cols-3">
        {/* Stage */}
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">
            Stage
          </p>
          {getStageBadge(currentStage) || (
            <span className="text-sm text-slate-500">Not started</span>
          )}
        </div>

        {/* Progress */}
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">
            Progress
          </p>
          <ProgressBar progress={progress} />
        </div>

        {/* GPU */}
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">GPU</p>
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-slate-500" />
            <span className="text-sm text-slate-300">{gpuType || "Not assigned"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
