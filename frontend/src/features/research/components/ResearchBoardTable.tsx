"use client";

import { useMemo } from "react";
import Link from "next/link";
import { Eye, AlertCircle, Package, Cpu, User, ArrowRight, Activity } from "lucide-react";
import type { ResearchRun } from "@/shared/lib/api-adapters";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { getStatusBadge } from "../utils/research-utils";

interface ResearchBoardTableProps {
  researchRuns: ResearchRun[];
}

function truncateRunId(runId: string): string {
  if (runId.length <= 14) return runId;
  return `${runId.slice(0, 14)}...`;
}

function getStageBadge(stage: string | null) {
  if (!stage) return null;

  const stageColors: Record<string, string> = {
    baseline: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    tuning: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    plotting: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
    ablation: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  };

  // Check if stage contains any of the known stage types
  const stageKey = Object.keys(stageColors).find(key => stage.toLowerCase().includes(key));
  const colorClass = stageKey
    ? stageColors[stageKey]
    : "bg-slate-500/15 text-slate-400 border-slate-500/30";

  return (
    <span className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-medium ${colorClass}`}>
      {stage}
    </span>
  );
}

function ProgressBar({ progress }: { progress: number | null }) {
  if (progress === null || progress === undefined) {
    return <span className="text-sm text-slate-500">No progress yet</span>;
  }

  const percentage = Math.round(progress * 100);

  return (
    <div className="flex items-center gap-3">
      <div className="h-2 w-32 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-sm font-medium text-slate-300">{percentage}%</span>
    </div>
  );
}

export function ResearchBoardTable({ researchRuns }: ResearchBoardTableProps) {
  const cards = useMemo(() => {
    return researchRuns.map(run => ({
      runId: run.runId,
      displayRunId: truncateRunId(run.runId),
      ideaTitle: run.ideaTitle || "Untitled",
      ideaHypothesis: run.ideaHypothesis,
      status: run.status,
      currentStage: run.currentStage,
      progress: run.progress,
      gpuType: run.gpuType,
      bestMetric: run.bestMetric,
      createdByName: run.createdByName,
      createdAt: formatRelativeTime(run.createdAt),
      artifactsCount: run.artifactsCount,
      errorMessage: run.errorMessage,
      conversationId: run.conversationId,
    }));
  }, [researchRuns]);

  if (cards.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-center">
          <h3 className="text-lg font-medium text-slate-300">No research runs found</h3>
          <p className="mt-1 text-sm text-slate-500">
            Start a research pipeline run from a conversation.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      {cards.map(card => (
        <div
          key={card.runId}
          className="group rounded-xl border border-slate-800 bg-slate-900/50 transition-all hover:border-slate-700 hover:bg-slate-900/80"
        >
          {/* Header: Run ID + Status */}
          <div className="flex items-center justify-between border-b border-slate-800/50 px-5 py-3">
            <span className="font-mono text-sm text-slate-500">{card.displayRunId}</span>
            {getStatusBadge(card.status)}
          </div>

          {/* Body */}
          <div className="p-5">
            {/* Title */}
            <h3 className="text-lg font-semibold text-white">{card.ideaTitle}</h3>

            {/* Hypothesis */}
            {card.ideaHypothesis && (
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{card.ideaHypothesis}</p>
            )}

            {/* Error Message for Failed Runs */}
            {card.status === "failed" && card.errorMessage && (
              <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
                <div className="flex items-start gap-2">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" />
                  <p className="text-sm text-red-300">{card.errorMessage}</p>
                </div>
              </div>
            )}

            {/* Stats Grid */}
            <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {/* Stage */}
              <div>
                <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">
                  Stage
                </p>
                {getStageBadge(card.currentStage) || (
                  <span className="text-sm text-slate-500">Not started</span>
                )}
              </div>

              {/* Progress */}
              <div>
                <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">
                  Progress
                </p>
                <ProgressBar progress={card.progress} />
              </div>

              {/* GPU */}
              <div>
                <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">
                  GPU
                </p>
                <div className="flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-slate-500" />
                  <span className="text-sm text-slate-300">{card.gpuType || "Not assigned"}</span>
                </div>
              </div>

              {/* Best Metric */}
              <div>
                <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">
                  Best Metric
                </p>
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-slate-500" />
                  <span className="text-sm text-slate-300">{card.bestMetric || "-"}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between border-t border-slate-800/50 px-5 py-3">
            <div className="flex items-center gap-4 text-sm text-slate-400">
              <div className="flex items-center gap-1.5">
                <User className="h-4 w-4" />
                <span>{card.createdByName}</span>
              </div>
              <span>•</span>
              <span>{card.createdAt}</span>
              {card.artifactsCount > 0 && (
                <>
                  <span>•</span>
                  <div className="flex items-center gap-1.5">
                    <Package className="h-4 w-4" />
                    <span>
                      {card.artifactsCount} artifact{card.artifactsCount !== 1 ? "s" : ""}
                    </span>
                  </div>
                </>
              )}
            </div>

            <Link
              href={`/research/${card.runId}`}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-500/15 px-4 py-2 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/25"
            >
              <Eye className="h-4 w-4" />
              View Details
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      ))}
    </div>
  );
}
