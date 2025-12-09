"use client";

/**
 * Loading skeleton for Ideation Queue cards.
 * Shows 5 placeholder cards while conversations are loading.
 */
export function IdeationQueueSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[1, 2, 3, 4, 5].map(i => (
        <div
          key={i}
          className="animate-pulse rounded-xl border border-slate-800 bg-slate-900/50 p-4"
        >
          {/* Status badge skeleton */}
          <div className="mb-3 h-5 w-20 rounded-full bg-slate-700/50" />

          {/* Title skeleton */}
          <div className="mb-2 h-5 w-3/4 rounded bg-slate-700/50" />

          {/* Abstract skeleton */}
          <div className="mb-3 space-y-1.5">
            <div className="h-4 w-full rounded bg-slate-700/50" />
            <div className="h-4 w-5/6 rounded bg-slate-700/50" />
          </div>

          {/* Footer skeleton (dates + button) */}
          <div className="flex items-center justify-between">
            <div className="flex gap-3">
              <div className="h-3 w-20 rounded bg-slate-700/50" />
              <div className="h-3 w-20 rounded bg-slate-700/50" />
            </div>
            <div className="h-6 w-16 rounded bg-slate-700/50" />
          </div>
        </div>
      ))}
    </div>
  );
}
