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
 * Supports expand/collapse to show research runs
 * Supports selection for inline view (if onSelect provided)
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
  isSelected,
  onSelect,
}: IdeationQueueCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const router = useRouter();
  const canLaunchResearch = status !== "no_idea";

  // Call onSelect if provided, otherwise navigate (backward compatible)
  const handleCardClick = () => {
    if (onSelect) {
      onSelect(id);
    } else {
      router.push(`/conversations/${id}`);
    }
  };

  const handleExpandToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded(prev => !prev);
  };

  const handleEditClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    router.push(`/conversations/${id}`);
  };

  return (
    <>
      <article
        onClick={handleCardClick}
        className={cn(
          "group cursor-pointer rounded-xl border border-slate-800 bg-slate-900/50 p-4",
          "transition-all hover:border-slate-700 hover:bg-slate-900/80",
          isSelected && "ring-2 ring-sky-500 border-sky-500/50 bg-slate-900/80"
        )}
      >
        {/* Header: Title + Edit Button */}
        <div className="mb-3 flex flex-row items-start justify-between gap-2">
          <h3 className="line-clamp-2 text-sm font-semibold text-slate-100 flex-1">{title}</h3>
          <Button
            onClick={handleEditClick}
            variant="ghost"
            size="sm"
            className="text-slate-400 hover:text-slate-300 shrink-0"
            aria-label="Edit conversation"
          >
            <Pencil className="h-3 w-3" />
            Edit
          </Button>
        </div>

        {/* Body: Markdown preview */}
        {markdown && (
          <div className="mb-3 line-clamp-3 text-xs leading-relaxed text-slate-400 prose-sm prose-invert max-w-none [&_p]:my-0 [&_h1]:hidden [&_h2]:hidden [&_h3]:hidden [&_h4]:hidden [&_h5]:hidden [&_h6]:hidden [&_ul]:my-0 [&_ol]:my-0 [&_li]:my-0">
            <Markdown>{markdown}</Markdown>
          </div>
        )}

        {/* Footer: Status + Toggle */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3 text-[10px] uppercase tracking-wide text-slate-500">
            <ConversationStatusBadge status={conversationStatus} />
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Created {formatRelativeTime(createdAt)}
            </span>
            <span>Updated {formatRelativeTime(updatedAt)}</span>
          </div>

          <button
            onClick={handleExpandToggle}
            type="button"
            aria-label={isExpanded ? "Hide research runs" : "Show research runs"}
            aria-expanded={isExpanded}
            className={cn(
              "inline-flex items-center gap-1 rounded px-2 py-1",
              "text-[10px] uppercase tracking-wide text-slate-400",
              "transition-colors hover:bg-slate-800 hover:text-slate-300"
            )}
          >
            {isExpanded ? "Hide Runs" : "Show Runs"}
            {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>

        {/* Expandable Runs Section */}
        {isExpanded && <IdeationQueueRunsList conversationId={id} />}

        {canLaunchResearch && (
          <div className="mt-4 flex items-center justify-end">
            <LaunchResearchButton conversationId={id} />
          </div>
        )}
      </article>
    </>
  );
}

// Memoize to prevent re-renders when parent filters change
export const IdeationQueueCard = memo(IdeationQueueCardComponent);
