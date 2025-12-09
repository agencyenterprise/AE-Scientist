import { memo } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { getStatusBadge, truncateRunId } from "@/features/research/utils/research-utils";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { cn } from "@/shared/lib/utils";
import type { IdeationQueueRunItemProps } from "../types/ideation-queue.types";

/**
 * Displays a single research run as a compact, clickable row.
 * Navigates to the research detail page when clicked.
 * Memoized to prevent unnecessary re-renders in lists.
 */
function IdeationQueueRunItemComponent({
  runId,
  status,
  gpuType,
  createdAt,
}: IdeationQueueRunItemProps) {
  const router = useRouter();

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation(); // Prevent card navigation
    e.preventDefault();
    router.push(`/research/${runId}`);
  };

  return (
    <button
      onClick={handleClick}
      type="button"
      aria-label={`View research run ${truncateRunId(runId)}, status: ${status}`}
      className={cn(
        "flex w-full items-center justify-between gap-3",
        "rounded-lg border border-slate-800/50 bg-slate-900/30",
        "px-3 py-2 text-left",
        "transition-colors hover:border-slate-700 hover:bg-slate-800/50"
      )}
    >
      <div className="flex items-center gap-3">
        {getStatusBadge(status, "sm")}
        <span className="font-mono text-xs text-slate-400">{truncateRunId(runId)}</span>
      </div>
      <div className="flex items-center gap-3 text-[10px] text-slate-500">
        {gpuType && <span className="hidden sm:inline">{gpuType}</span>}
        <span>{formatRelativeTime(createdAt)}</span>
        <ArrowRight className="h-3 w-3 text-slate-600" />
      </div>
    </button>
  );
}

export const IdeationQueueRunItem = memo(IdeationQueueRunItemComponent);
