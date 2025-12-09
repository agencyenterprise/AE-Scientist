import { useConversationResearchRuns } from "../hooks/useConversationResearchRuns";
import { IdeationQueueRunItem } from "./IdeationQueueRunItem";
import type { IdeationQueueRunsListProps } from "../types/ideation-queue.types";

/**
 * Loading skeleton for the runs list.
 * Displays 3 placeholder rows with animation.
 */
function RunsListSkeleton() {
  return (
    <div className="mt-3 space-y-2 border-t border-slate-800 pt-3">
      {[1, 2, 3].map(i => (
        <div
          key={i}
          className="animate-pulse rounded-lg border border-slate-800/50 bg-slate-900/30 px-3 py-2"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-6 w-16 rounded-full bg-slate-700/50" />
              <div className="h-4 w-24 rounded bg-slate-700/50" />
            </div>
            <div className="flex items-center gap-3">
              <div className="h-3 w-16 rounded bg-slate-700/50" />
              <div className="h-3 w-3 rounded bg-slate-700/50" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Empty state when no research runs exist.
 */
function RunsListEmpty() {
  return (
    <div className="mt-3 border-t border-slate-800 pt-3">
      <div className="flex h-12 items-center justify-center">
        <p className="text-sm text-slate-500">No research runs yet</p>
      </div>
    </div>
  );
}

/**
 * Error state with retry capability.
 */
function RunsListError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="mt-3 border-t border-slate-800 pt-3">
      <div className="flex items-center justify-between rounded-lg bg-red-500/10 px-3 py-2 text-sm">
        <span className="text-red-400">{message}</span>
        <button
          onClick={e => {
            e.stopPropagation();
            onRetry();
          }}
          type="button"
          className="text-xs text-red-300 hover:text-red-200"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

/**
 * Container component that fetches and displays research runs for a conversation.
 * Handles loading, empty, and error states.
 */
export function IdeationQueueRunsList({ conversationId }: IdeationQueueRunsListProps) {
  const { runs, isLoading, error, refetch } = useConversationResearchRuns(conversationId);

  // Loading state
  if (isLoading) {
    return <RunsListSkeleton />;
  }

  // Error state
  if (error) {
    return <RunsListError message={error} onRetry={refetch} />;
  }

  // Empty state
  if (!runs || runs.length === 0) {
    return <RunsListEmpty />;
  }

  // Runs list (limit to 5 most recent)
  const displayRuns = runs.slice(0, 5);
  const hasMore = runs.length > 5;

  return (
    <div className="mt-3 border-t border-slate-800 pt-3">
      <div className="space-y-2">
        {displayRuns.map(run => (
          <IdeationQueueRunItem
            key={run.run_id}
            runId={run.run_id}
            status={run.status}
            gpuType={run.gpu_type ?? null}
            createdAt={run.created_at}
          />
        ))}
      </div>
      {hasMore && (
        <div className="mt-2 text-center">
          <span className="text-xs text-slate-500">+{runs.length - 5} more runs</span>
        </div>
      )}
    </div>
  );
}
