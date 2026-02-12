"use client";

import { memo, useState } from "react";
import { useRouter } from "next/navigation";
import { Clock, ChevronDown, ChevronUp, Pencil } from "lucide-react";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/components/ui/button";
import { Markdown } from "@/shared/components/Markdown";
import type { IdeationQueueCardProps } from "@/features/conversation";
import { ConversationStatusBadge } from "./ConversationStatusBadge";
import { IdeationQueueRunsList } from "./IdeationQueueRunsList";
import { LaunchResearchButton } from "./LaunchResearchButton";

/**
 * Card component for displaying a single idea in the Ideation Queue
 * Supports expand/collapse for content and research runs
 * Memoized for performance in list rendering
 */
function IdeationQueueCardComponent({
  id,
  title,
  markdown,
  status,
  createdAt,
  updatedAt,
  conversationStatus = "draft",
}: IdeationQueueCardProps) {
  const [isRunsExpanded, setIsRunsExpanded] = useState(true);
  const [isContentExpanded, setIsContentExpanded] = useState(false);
  const router = useRouter();
  const canLaunchResearch = status !== "no_idea";

  const handleRunsToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsRunsExpanded(prev => !prev);
  };

  const handleContentToggle = () => {
    setIsContentExpanded(prev => !prev);
  };

  const handleRefineClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    router.push(`/ideation-queue/${id}`);
  };

  return (
    <>
      <article
        className={cn(
          "group rounded-2xl border border-slate-800 bg-slate-900/50 p-3 sm:p-4",
          "transition-all hover:border-slate-700 hover:bg-slate-900/80"
        )}
      >
        {/* Header: Title + Refine Button */}
        <div className="mb-3 flex flex-row items-start justify-between gap-2">
          <h3 className="line-clamp-2 text-sm font-semibold text-slate-100 flex-1">{title}</h3>
          <Button
            onClick={handleRefineClick}
            variant="ghost"
            size="sm"
            className="text-slate-400 hover:text-slate-300 shrink-0 px-2 sm:px-3"
            aria-label="Refine research idea"
          >
            <Pencil className="h-3 w-3" />
            <span className="hidden sm:inline">Refine further</span>
          </Button>
        </div>

        {/* Body: Markdown content - click to expand/collapse */}
        {markdown && (
          <div
            onClick={handleContentToggle}
            className={cn(
              "mb-3 text-xs leading-relaxed text-slate-400 prose-sm prose-invert max-w-none cursor-pointer",
              "[&_p]:my-0 [&_h1]:hidden [&_h2]:hidden [&_h3]:hidden [&_h4]:hidden [&_h5]:hidden [&_h6]:hidden [&_ul]:my-0 [&_ol]:my-0 [&_li]:my-0",
              !isContentExpanded && "line-clamp-3"
            )}
          >
            <Markdown>{markdown}</Markdown>
          </div>
        )}

        {/* Footer: Status + Toggle */}
        <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
          <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-[10px] uppercase tracking-wide text-slate-500">
            <ConversationStatusBadge status={conversationStatus} />
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Created {formatRelativeTime(createdAt)}
            </span>
            <span className="hidden sm:inline">Updated {formatRelativeTime(updatedAt)}</span>
          </div>

          <button
            onClick={handleRunsToggle}
            type="button"
            aria-label={isRunsExpanded ? "Hide research runs" : "Show research runs"}
            aria-expanded={isRunsExpanded}
            className={cn(
              "inline-flex items-center gap-1 rounded px-2 py-1 shrink-0",
              "text-[10px] uppercase tracking-wide text-slate-400",
              "transition-colors hover:bg-slate-800 hover:text-slate-300"
            )}
          >
            {isRunsExpanded ? "Hide Runs" : "Show Runs"}
            {isRunsExpanded ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </button>
        </div>

        {/* Expandable Runs Section */}
        {isRunsExpanded && <IdeationQueueRunsList conversationId={id} />}

        {canLaunchResearch && (
          <div className="mt-3 sm:mt-4 flex items-center justify-center sm:justify-end">
            <LaunchResearchButton conversationId={id} />
          </div>
        )}
      </article>
    </>
  );
}

// Memoize to prevent re-renders when parent filters change
export const IdeationQueueCard = memo(IdeationQueueCardComponent);
