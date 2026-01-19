import { Skeleton } from "@/shared/components/ui/skeleton";

/**
 * Loading skeleton for timeline.
 */
export function NarrativePageLoading() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map(i => (
        <div key={i} className="border border-slate-700/50 rounded-lg overflow-hidden">
          {/* Header skeleton */}
          <div className="px-4 py-3 bg-slate-900/95">
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-48 bg-slate-800/50" />
                <Skeleton className="h-3 w-32 bg-slate-800/50" />
              </div>
              <Skeleton className="h-8 w-24 bg-slate-800/50" />
            </div>
          </div>

          {/* Content skeleton */}
          <div className="p-4 space-y-3 bg-slate-900/30">
            <Skeleton className="h-24 w-full bg-slate-800/50" />
            <Skeleton className="h-24 w-full bg-slate-800/50" />
          </div>
        </div>
      ))}
    </div>
  );
}
