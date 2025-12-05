"use client";

import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { Clock } from "lucide-react";
import type { ResearchRun } from "@/types/research";

interface ResearchHistoryCardProps {
  research: ResearchRun;
}

/**
 * Card displaying a single research run for the home page history.
 * Styled to match orchestrator/components/HypothesisHistoryList.tsx
 */
export function ResearchHistoryCard({ research }: ResearchHistoryCardProps) {
  const createdAt = new Date(research.createdAt);
  const relativeCreated = formatDistanceToNow(createdAt, { addSuffix: true });
  const launchedAt = research.updatedAt ? new Date(research.updatedAt) : createdAt;

  const isRunning = research.status === "running";
  const isPending = research.status === "pending";
  const isFailed = research.status === "failed";
  const isCompleted = research.status === "completed";

  return (
    <Link href={`/research/${research.runId}`}>
      <article className="group relative overflow-hidden rounded-[1.75rem] border border-slate-800/70 bg-slate-950/70 p-5 transition hover:border-sky-500/60">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1 space-y-3">
            {/* Title with status badge */}
            <div className="flex flex-wrap items-center gap-2">
              <p className="break-words text-sm font-semibold leading-snug text-slate-100 line-clamp-2">
                {research.ideaTitle || "Untitled Research"}
              </p>
              {isRunning && (
                <span className="inline-flex items-center gap-1 rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-200">
                  running {research.currentStage || ""}
                </span>
              )}
              {isPending && (
                <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-200">
                  waiting on ideation
                </span>
              )}
              {isFailed && (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-200">
                  failed
                </span>
              )}
              {isCompleted && (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-200">
                  completed
                </span>
              )}
            </div>

            {/* Ideation Highlight section */}
            {research.ideaHypothesis && (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
                  Ideation highlight
                </p>
                <p className="line-clamp-4 whitespace-pre-line text-xs leading-relaxed text-slate-300">
                  {research.ideaHypothesis}
                </p>
              </div>
            )}

            {/* Timestamp pills */}
            <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.3em] text-slate-500">
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-800/80 bg-slate-900/70 px-3 py-1 font-semibold">
                <Clock className="h-3 w-3 text-slate-400" />
                {relativeCreated}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-slate-800/60 bg-slate-900/60 px-3 py-1 font-medium text-slate-200">
                launched {launchedAt.toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      </article>
    </Link>
  );
}
