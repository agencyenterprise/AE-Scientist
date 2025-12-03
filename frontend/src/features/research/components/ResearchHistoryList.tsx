"use client";

import { useRecentResearch } from "../hooks/useRecentResearch";
import { ResearchHistoryCard } from "./ResearchHistoryCard";
import { ResearchHistoryEmpty } from "./ResearchHistoryEmpty";
import { ResearchHistorySkeleton } from "./ResearchHistorySkeleton";
import { AlertCircle, Lightbulb } from "lucide-react";

/**
 * Container component for research history section on home page.
 * Styled to match orchestrator/components/HypothesisHistoryList.tsx
 * Handles loading, empty, error, and data states.
 */
export function ResearchHistoryList() {
  const { researchRuns, isLoading, error, refetch } = useRecentResearch();

  const entryCount = researchRuns.length;

  // Don't render anything if empty and not loading
  if (!isLoading && !error && entryCount === 0) {
    return <ResearchHistoryEmpty />;
  }

  return (
    <section className="rounded-[2.4rem] border border-slate-800/70 bg-slate-950/70 p-6 shadow-[0_40px_120px_-70px_rgba(14,165,233,0.8)]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-sky-200">
          <Lightbulb className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-[0.35em]">
            Research History
          </span>
        </div>
        {!isLoading && entryCount > 0 && (
          <span className="text-[11px] uppercase tracking-[0.3em] text-slate-500">
            Last {entryCount} entries
          </span>
        )}
      </div>

      {/* Content Area */}
      {isLoading && (
        <div className="mt-6">
          <ResearchHistorySkeleton />
        </div>
      )}

      {error && !isLoading && (
        <div className="mt-6 flex flex-col items-center gap-2 py-8">
          <AlertCircle className="h-6 w-6 text-red-400" />
          <p className="text-sm text-red-400">{error}</p>
          <button
            onClick={() => refetch()}
            className="text-xs text-slate-400 underline hover:text-slate-300"
          >
            Try again
          </button>
        </div>
      )}

      {!isLoading && !error && entryCount > 0 && (
        <div className="mt-6 grid gap-4">
          {researchRuns.map(research => (
            <ResearchHistoryCard key={research.runId} research={research} />
          ))}
        </div>
      )}
    </section>
  );
}
