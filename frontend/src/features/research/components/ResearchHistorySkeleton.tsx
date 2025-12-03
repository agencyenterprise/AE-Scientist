"use client";

/**
 * Loading skeleton for research history cards.
 * Shows 3 placeholder cards while data is loading.
 */
export function ResearchHistorySkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map(i => (
        <div
          key={i}
          className="animate-pulse rounded-lg border border-slate-800 bg-slate-900/50 p-4"
        >
          {/* Header skeleton */}
          <div className="mb-2 flex items-center justify-between">
            <div className="h-6 w-20 rounded-full bg-slate-700/50" />
            <div className="h-4 w-24 rounded bg-slate-700/50" />
          </div>

          {/* Title skeleton */}
          <div className="mb-2 h-5 w-3/4 rounded bg-slate-700/50" />

          {/* Description skeleton */}
          <div className="mb-3 space-y-1.5">
            <div className="h-4 w-full rounded bg-slate-700/50" />
            <div className="h-4 w-5/6 rounded bg-slate-700/50" />
          </div>

          {/* Button skeleton */}
          <div className="flex justify-end">
            <div className="h-7 w-24 rounded-lg bg-slate-700/50" />
          </div>
        </div>
      ))}
    </div>
  );
}
